@tool
extends RefCounted
## Validate one coherent copy of disk files plus unsaved source overlays.
## Godot compiler caches and live class reloads never determine these results.
var host: EditorPlugin
const MAX_FILES := 20000
const MAX_BYTES := 512 * 1024 * 1024
const EXCLUDED := [".git", ".godot", ".godot-mcp", ".venv", ".pytest_cache", ".ruff_cache"]
const ProcessOutput = preload("res://addons/godot_mcp/process_output.gd")

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

func _walk_tree(source: String, target: String, budget: Array, manifest: Dictionary, excluded: Array[String], symlinks: Array[String], copy_files: bool, relative: String = "") -> String:
	var directory := DirAccess.open(source)
	if not directory: return "Cannot read project directory: " + source
	if copy_files and DirAccess.make_dir_recursive_absolute(target) != OK: return "Cannot create validation directory."
	directory.list_dir_begin()
	var name: String = directory.get_next()
	while not name.is_empty():
		if name in EXCLUDED:
			excluded.append(relative.path_join(name))
			name = directory.get_next()
			continue
		var from: String = source.path_join(name)
		var to: String = target.path_join(name)
		if directory.is_link(name):
			symlinks.append(relative.path_join(name))
			name = directory.get_next()
			continue
		if directory.current_is_dir():
			var message: String = _walk_tree(from, to, budget, manifest, excluded, symlinks, copy_files, relative.path_join(name))
			if not message.is_empty(): return message
		else:
			var file := FileAccess.open(from, FileAccess.READ)
			if not file: return "Cannot read project file: " + from
			budget[0] += 1
			budget[1] += file.get_length()
			file.close()
			if budget[0] > MAX_FILES or budget[1] > MAX_BYTES: return "Validation snapshot exceeds 20000 files or 512 MiB."
			if copy_files and DirAccess.copy_absolute(from, to) != OK: return "Cannot copy project file: " + from
			var digest: String = _hash_file(to if copy_files else from)
			if digest.is_empty(): return "Cannot hash validation snapshot file: " + to
			manifest[relative.path_join(name)] = digest
		name = directory.get_next()
	directory.list_dir_end()
	return ""

func _copy_tree(source: String, target: String, budget: Array, manifest: Dictionary, excluded: Array[String], symlinks: Array[String]) -> String:
	return _walk_tree(source, target, budget, manifest, excluded, symlinks, true)

func _fingerprint_tree(source: String, manifest: Dictionary, budget: Array, excluded: Array[String], symlinks: Array[String]) -> String:
	return _walk_tree(source, "", budget, manifest, excluded, symlinks, false)

func _project_changed(project: String, captured: Dictionary, captured_symlinks: Array[String] = []) -> String:
	var current: Dictionary = {}
	var current_excluded: Array[String] = []
	var current_symlinks: Array[String] = []
	var message: String = _fingerprint_tree(project, current, [0, 0], current_excluded, current_symlinks)
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
	current_symlinks.sort()
	var previous_symlinks: Array[String] = captured_symlinks.duplicate()
	previous_symlinks.sort()
	if current_symlinks != previous_symlinks: changes.append("excluded symlink paths changed")
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
	var collected := ProcessOutput.new()
	while OS.is_process_running(pid):
		for key: String in ["stdio", "stderr"]:
			var pipe: FileAccess = process.get(key)
			if pipe:
				var bytes: PackedByteArray = pipe.get_buffer(8192)
				collected.append("stdout" if key == "stdio" else "stderr", bytes)
		if Time.get_ticks_msec() - start > timeout_ms:
			OS.kill(pid)
			var timeout_result: Dictionary = collected.result()
			return {"ok": false, "message": timeout_result.stdout + timeout_result.stderr, "truncated": timeout_result.truncated}
		OS.delay_msec(10)
	# Drain diagnostics emitted immediately before the child exited.
	for key: String in ["stdio", "stderr"]:
		var pipe: FileAccess = process.get(key)
		if not pipe: continue
		var bytes: PackedByteArray = pipe.get_buffer(8192)
		while not bytes.is_empty():
			collected.append("stdout" if key == "stdio" else "stderr", bytes)
			bytes = pipe.get_buffer(8192)
		pipe.close()
	var output: Dictionary = collected.result()
	var code: int = OS.get_process_exit_code(pid)
	return {"ok": code == 0, "message": output.stdout + output.stderr, "exit_code": code, "truncated": output.truncated}

func _affected_by_symlink(uri: String, source: String, symlinks: Array[String]) -> bool:
	var paths: Array[String] = [uri]
	var quoted := RegEx.new()
	quoted.compile("[\"']([^\"'\\n]+)[\"']")
	for match_value: RegExMatch in quoted.search_all(source):
		var value: String = match_value.get_string(1)
		paths.append(value if value.begins_with("res://") else uri.get_base_dir().path_join(value).simplify_path())
	for path: String in paths:
		var relative: String = path.trim_prefix("res://").get_slice("::", 0)
		for skipped: String in symlinks:
			if relative == skipped or relative.begins_with(skipped + "/"): return true
	return false

func _classify_excluded_dependencies(item: Dictionary, symlinks: Array[String]) -> Dictionary:
	if symlinks.is_empty(): return item
	var affected: bool = _affected_by_symlink(item.uri, "", symlinks)
	var uncertain: bool = false
	for entry: Dictionary in item.entries:
		if entry.get("kind") != "error": continue
		var message: String = str(entry.get("message", ""))
		if _affected_by_symlink(str(entry.get("uri", item.uri)), message, symlinks): affected = true
		# Missing global classes/indirect includes need not name the skipped path.
		# In that case an incomplete snapshot cannot settle source validity.
		var lower: String = message.to_lower()
		if ("preload" in lower and "does not exist" in lower) or "failed to compile depended scripts" in lower or "could not find base class" in lower or "could not resolve" in lower or "could not load shader include" in lower:
			uncertain = true
	if affected or uncertain:
		item.state = "unavailable"
		item.valid = null
		item.excluded_paths = symlinks.duplicate()
		item.entries.append({"kind": "warning", "uri": item.uri, "line": 0, "origin": "snapshot", "message": "A dependency uses an excluded symlinked path." if affected else "Dependency resolution failed while symlinked paths were excluded; this snapshot cannot determine source validity."})
	return item

func _check_script(executable: String, snapshot: String, uri: String, revisions: Dictionary, autoloads: Dictionary, timeout_ms: int) -> Dictionary:
	# Do not start scenes or autoloads. Godot can still run static initializers
	# while compiling preloads; this is a compiler snapshot, not an OS sandbox.
	var checked: Dictionary = _execute(executable, ["--headless", "--editor", "--path", snapshot, "--check-only", "--script", uri], timeout_ms)
	if not checked.has("exit_code"):
		return unavailable([uri], revisions, str(checked.message) + (" (process output truncated)." if checked.get("truncated", false) else "")).sources[0]
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
		return unavailable([uri], revisions, "Godot check-only failed: " + str(checked.message) + (" (process output truncated)." if checked.get("truncated", false) else "")).sources[0]
	if checked.get("truncated", false):
		var incomplete: Dictionary = unavailable([uri], revisions, "Compiler output was truncated; a complete validation result is unavailable.").sources[0]
		incomplete.entries.append_array(entries)
		return incomplete
	# Godot can return exit code 0 after dependency compilation fails. Its
	# source diagnostics are part of the verdict, not just accompanying text.
	var valid: bool = checked.ok and entries.is_empty()
	return {"uri": uri, "revision": revisions.get(uri), "state": "valid" if valid else "invalid", "valid": valid, "scope": "snapshot", "entries": entries}

func _run(project: String, executable: String, uris: Array, overlays: Dictionary, revisions: Dictionary) -> Dictionary:
	var deadline: int = Time.get_ticks_msec() + 60000
	var snapshot: String = OS.get_cache_dir().path_join("godot-mcp-validation-" + Crypto.new().generate_random_bytes(12).hex_encode())
	var manifest: Dictionary = {}
	var excluded: Array[String] = []
	var symlinks: Array[String] = []
	var message: String = _copy_tree(project, snapshot, [0, 0], manifest, excluded, symlinks)
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
			if _affected_by_symlink(uri, "", symlinks):
				result.sources.append(unavailable([uri], revisions, "Validation source or dependency is unavailable because a symlinked project path was skipped.").sources[0])
				continue
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
		for item: Dictionary in result.sources: _classify_excluded_dependencies(item, symlinks)
		message = _project_changed(project, manifest, symlinks)
		result.sources.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return uris.find(a.uri) < uris.find(b.uri))
		result.snapshot_id = snapshot.get_file()
		result.source_revisions = revisions
	_remove_tree(snapshot)
	return result if message.is_empty() else unavailable(uris, revisions, message)
