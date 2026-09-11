@tool
extends RefCounted
## Validate one coherent copy of disk files plus unsaved source overlays.
## Godot compiler caches and live class reloads never determine these results.
var host: EditorPlugin
const MAX_FILES := 20000
const MAX_BYTES := 512 * 1024 * 1024
const EXCLUDED := [".git", ".godot", ".godot-mcp", ".venv", ".pytest_cache", ".ruff_cache"]

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func check(uris: Array, overlays: Dictionary, revisions: Dictionary) -> Dictionary:
	var worker := Thread.new()
	var project: String = ProjectSettings.globalize_path("res://")
	var executable: String = OS.get_executable_path()
	var error: Error = worker.start(_run.bind(project, executable, uris.duplicate(), overlays.duplicate(true), revisions.duplicate(true)))
	if error != OK: return unavailable(uris, revisions, "Cannot start the validation worker.")
	while worker.is_alive():
		await host.get_tree().process_frame
	return worker.wait_to_finish()

func unavailable(uris: Array, revisions: Dictionary, message: String) -> Dictionary:
	var sources: Array = []
	for uri: String in uris:
		sources.append({"uri": uri, "revision": revisions.get(uri), "state": "unavailable", "valid": null, "scope": "snapshot", "entries": [{"kind": "error", "uri": uri, "line": 0, "message": message}]})
	return {"sources": sources}

func _hash_file(path: String) -> String:
	var file := FileAccess.open(path, FileAccess.READ)
	if not file: return ""
	var hashing := HashingContext.new()
	if hashing.start(HashingContext.HASH_SHA256) != OK:
		file.close()
		return ""
	while not file.eof_reached(): hashing.update(file.get_buffer(1024 * 1024))
	file.close()
	return hashing.finish().hex_encode()

func _copy_tree(source: String, target: String, budget: Array, manifest: Dictionary, relative: String = "") -> String:
	var directory := DirAccess.open(source)
	if not directory: return "Cannot read project directory: " + source
	if DirAccess.make_dir_recursive_absolute(target) != OK: return "Cannot create validation directory."
	directory.list_dir_begin()
	var name: String = directory.get_next()
	while not name.is_empty():
		if name in EXCLUDED:
			name = directory.get_next()
			continue
		var from: String = source.path_join(name)
		var to: String = target.path_join(name)
		if directory.is_link(name): return "Snapshot validation does not follow symlinks: " + from
		if directory.current_is_dir():
			var message: String = _copy_tree(from, to, budget, manifest, relative.path_join(name))
			if not message.is_empty(): return message
		else:
			var file := FileAccess.open(from, FileAccess.READ)
			if not file: return "Cannot read project file: " + from
			budget[0] += 1
			budget[1] += file.get_length()
			file.close()
			if budget[0] > MAX_FILES or budget[1] > MAX_BYTES: return "Validation snapshot exceeds 20000 files or 512 MiB."
			if DirAccess.copy_absolute(from, to) != OK: return "Cannot copy project file: " + from
			var digest: String = _hash_file(to)
			if digest.is_empty(): return "Cannot hash validation snapshot file: " + to
			manifest[relative.path_join(name)] = digest
		name = directory.get_next()
	directory.list_dir_end()
	return ""

func _fingerprint_tree(source: String, manifest: Dictionary, budget: Array, relative: String = "") -> String:
	var directory := DirAccess.open(source)
	if not directory: return "Cannot read project directory during validation: " + source
	directory.list_dir_begin()
	var name: String = directory.get_next()
	while not name.is_empty():
		if name in EXCLUDED:
			name = directory.get_next()
			continue
		var path: String = source.path_join(name)
		var key: String = relative.path_join(name)
		if directory.is_link(name): return "Project changed during validation: symlink encountered at " + path
		if directory.current_is_dir():
			var message: String = _fingerprint_tree(path, manifest, budget, key)
			if not message.is_empty(): return message
		else:
			var file := FileAccess.open(path, FileAccess.READ)
			if not file: return "Cannot read project file during validation: " + path
			budget[0] += 1
			budget[1] += file.get_length()
			file.close()
			if budget[0] > MAX_FILES or budget[1] > MAX_BYTES: return "Validation fingerprint exceeds 20000 files or 512 MiB."
			var digest: String = _hash_file(path)
			if digest.is_empty(): return "Cannot hash project file during validation: " + path
			manifest[key] = digest
		name = directory.get_next()
	directory.list_dir_end()
	return ""

func _project_changed(project: String, captured: Dictionary) -> String:
	var current: Dictionary = {}
	var message: String = _fingerprint_tree(project, current, [0, 0])
	if not message.is_empty(): return message
	var added: Array[String] = []
	var deleted: Array[String] = []
	var modified: Array[String] = []
	for path: String in current:
		if not captured.has(path): added.append(path)
		elif captured[path] != current[path]: modified.append(path)
	for path: String in captured:
		if not current.has(path): deleted.append(path)
	added.sort()
	deleted.sort()
	modified.sort()
	var changes: Array[String] = []
	if not added.is_empty(): changes.append("added: " + ", ".join(added))
	if not deleted.is_empty(): changes.append("deleted: " + ", ".join(deleted))
	if not modified.is_empty(): changes.append("modified: " + ", ".join(modified))
	return "" if changes.is_empty() else "Project changed during validation (" + "; ".join(changes) + ")."

func _remove_tree(path: String) -> void:
	var directory := DirAccess.open(path)
	if not directory: return
	directory.list_dir_begin()
	var name: String = directory.get_next()
	while not name.is_empty():
		var item: String = path.path_join(name)
		if directory.current_is_dir() and not directory.is_link(name): _remove_tree(item)
		else: DirAccess.remove_absolute(item)
		name = directory.get_next()
	directory.list_dir_end()
	DirAccess.remove_absolute(path)

func _execute(executable: String, arguments: PackedStringArray, timeout_ms: int) -> Dictionary:
	var process: Dictionary = OS.execute_with_pipe(executable, arguments, false)
	if process.is_empty(): return {"ok": false, "message": "Cannot start the Godot validator."}
	var pid: int = int(process.pid)
	var start: int = Time.get_ticks_msec()
	var output: String = ""
	while OS.is_process_running(pid):
		for key: String in ["stdio", "stderr"]:
			var pipe: FileAccess = process.get(key)
			if pipe:
				var bytes: PackedByteArray = pipe.get_buffer(8192)
				if output.length() < 16000: output += bytes.get_string_from_utf8()
		if Time.get_ticks_msec() - start > timeout_ms:
			OS.kill(pid)
			return {"ok": false, "message": "Godot snapshot validation timed out."}
		OS.delay_msec(10)
	# Drain diagnostics emitted immediately before the child exited.
	for key: String in ["stdio", "stderr"]:
		var pipe: FileAccess = process.get(key)
		if not pipe: continue
		var bytes: PackedByteArray = pipe.get_buffer(8192)
		while not bytes.is_empty():
			if output.length() < 16000: output += bytes.get_string_from_utf8()
			bytes = pipe.get_buffer(8192)
		pipe.close()
	var code: int = OS.get_process_exit_code(pid)
	return {"ok": code == 0, "message": output, "exit_code": code}

func _check_script(executable: String, snapshot: String, uri: String, revisions: Dictionary, autoloads: Dictionary, timeout_ms: int) -> Dictionary:
	# Do not start scenes or autoloads. Godot can still run static initializers
	# while compiling preloads; this is a compiler snapshot, not an OS sandbox.
	var checked: Dictionary = _execute(executable, ["--headless", "--editor", "--path", snapshot, "--check-only", "--script", uri], timeout_ms)
	if not checked.has("exit_code"):
		return unavailable([uri], revisions, checked.message).sources[0]
	var entries: Array = []
	var location := RegEx.new()
	location.compile("\\((res://.+):([0-9]+)\\)")
	var last: Dictionary = {}
	for line: String in str(checked.message).split("\n"):
		if line.begins_with("SCRIPT ERROR:"):
			last = {"kind": "error", "uri": uri, "line": 0, "message": line.trim_prefix("SCRIPT ERROR: "), "origin": "source"}
			entries.append(last)
		elif not last.is_empty():
			var matched: RegExMatch = location.search(line)
			if matched:
				last.uri = matched.get_string(1)
				last.line = int(matched.get_string(2))
				last.origin = "source" if last.uri == uri else "dependency"
				last = {}
	for name: String in autoloads:
		if str(autoloads[name]).begins_with("*") and (str(checked.message).contains("Identifier not found: " + name) or str(checked.message).contains('Identifier "' + name + '" not declared')):
			return unavailable([uri], revisions, "Godot check-only cannot resolve autoload singleton '" + name + "' without running it. Verify this source in the editor; no fresh validity claim is available.").sources[0]
	if not checked.ok and entries.is_empty():
		return unavailable([uri], revisions, "Godot check-only failed: " + str(checked.message)).sources[0]
	return {"uri": uri, "revision": revisions.get(uri), "state": "valid" if checked.ok else "invalid", "valid": checked.ok, "scope": "snapshot", "entries": entries}

func _run(project: String, executable: String, uris: Array, overlays: Dictionary, revisions: Dictionary) -> Dictionary:
	var deadline: int = Time.get_ticks_msec() + 60000
	var snapshot: String = OS.get_cache_dir().path_join("godot-mcp-validation-" + Crypto.new().generate_random_bytes(12).hex_encode())
	var manifest: Dictionary = {}
	var message: String = _copy_tree(project, snapshot, [0, 0], manifest)
	if message.is_empty():
		for uri: String in overlays:
			var target: String = snapshot.path_join(uri.trim_prefix("res://"))
			DirAccess.make_dir_recursive_absolute(target.get_base_dir())
			var file := FileAccess.open(target, FileAccess.WRITE)
			if not file:
				message = "Cannot write a source overlay."
				break
			file.store_string(str(overlays[uri]))
			file.close()
	var config := ConfigFile.new()
	var autoloads: Dictionary = {}
	if message.is_empty():
		if config.load(snapshot.path_join("project.godot")) != OK:
			message = "Cannot read snapshot project settings."
		else:
			# Import classes with no user scene, editor plugins, or autoload execution.
			if config.has_section("editor_plugins"): config.erase_section("editor_plugins")
			if config.has_section("autoload"):
				for name: String in config.get_section_keys("autoload"):
					autoloads[name] = config.get_value("autoload", name)
				config.erase_section("autoload")
			if config.has_section_key("application", "run/main_scene"): config.erase_section_key("application", "run/main_scene")
			if config.save(snapshot.path_join("project.godot")) != OK: message = "Cannot write snapshot project settings."
	if message.is_empty():
		var imported: Dictionary = _execute(executable, ["--headless", "--path", snapshot, "--editor", "--import", "--quit"], 15000)
		if not imported.ok: message = "Snapshot import failed: " + str(imported.message)
	var result: Dictionary = {"sources": []}
	var shaders: Array = []
	if message.is_empty():
		# Keep declared names/types for parsing. Check-only does not start autoloads.
		for name: String in autoloads: config.set_value("autoload", name, autoloads[name])
		config.save(snapshot.path_join("project.godot"))
		for uri: String in uris:
			if uri.ends_with(".gdshader"):
				shaders.append(uri)
			else:
				var remaining: int = deadline - Time.get_ticks_msec()
				result.sources.append(_check_script(executable, snapshot, uri, revisions, autoloads, mini(10000, remaining)) if remaining > 0 else unavailable([uri], revisions, "Validation batch exceeded its time budget.").sources[0])
	if message.is_empty() and not shaders.is_empty():
		# The shader helper runs, so disable all autoloads again before starting it.
		if config.has_section("autoload"): config.erase_section("autoload")
		config.save(snapshot.path_join("project.godot"))
		var request: String = snapshot.path_join(".godot-mcp-validation-request.json")
		var output: String = snapshot.path_join(".godot-mcp-validation-result.json")
		var file := FileAccess.open(request, FileAccess.WRITE)
		if not file: message = "Cannot write the validation request."
		else:
			file.store_string(JSON.stringify({"uris": shaders, "revisions": revisions}))
			file.close()
		if message.is_empty():
			var checked: Dictionary = _execute(executable, ["--headless", "--path", snapshot, "--script", "res://addons/godot_mcp/validation_runner.gd", "--", request, output], 10000)
			if not checked.ok: message = "Shader compiler failed: " + str(checked.message)
		if message.is_empty():
			var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(output))
			if parsed is Dictionary and parsed.get("sources") is Array: result.sources.append_array(parsed.sources)
			else: message = "Shader compiler returned no usable result."
	if message.is_empty():
		message = _project_changed(project, manifest)
		result.sources.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return uris.find(a.uri) < uris.find(b.uri))
		result.snapshot_id = snapshot.get_file()
		result.source_revisions = revisions
	_remove_tree(snapshot)
	return result if message.is_empty() else unavailable(uris, revisions, message)
