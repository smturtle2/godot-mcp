@tool
extends RefCounted
const ProcessOutput = preload("res://addons/godot_mcp/process_output.gd")
const FileJournal = preload("res://addons/godot_mcp/file_journal.gd")
const ImportOperations = preload("res://addons/godot_mcp/import_operations.gd")
var host: EditorPlugin
var imports: RefCounted

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host
	imports = ImportOperations.new(host, self)

func handles(method: String) -> bool:
	return method in ["get_settings", "update_settings", "get_export_presets", "export_build", "import_assets", "move_assets"]

func dispatch(method: String, p: Dictionary) -> Dictionary:
	match method:
		"get_settings": return get_settings(p)
		"update_settings": return update_settings(p)
		"get_export_presets": return get_export_presets(p)
		"export_build": return await export_build(p)
		"import_assets": return await import_assets(p)
		"move_assets": return await move_assets(p)
	return host.fail("UNKNOWN_TOOL", method)

func input_info(event: InputEvent) -> Dictionary:
	var info: Dictionary = {"class": event.get_class(), "description": event.as_text()}
	if event is InputEventKey:
		info.key = OS.get_keycode_string(event.keycode if event.keycode else event.physical_keycode)
		info.physical = event.physical_keycode != 0
	elif event is InputEventMouseButton: info.button = event.button_index
	elif event is InputEventJoypadButton: info.button = event.button_index
	elif event is InputEventJoypadMotion:
		info.axis = event.axis
		info.axis_value = event.axis_value
	return info

func get_settings(p: Dictionary) -> Dictionary:
	var include: Array = p.get("include", ["project", "input_actions", "autoload"])
	var result: Dictionary = {"settings": {}, "metadata": {}, "input_actions": [], "autoloads": []}
	for prop: Dictionary in ProjectSettings.get_property_list():
		var key: String = str(prop.name)
		if not p.get("keys", []).is_empty() and not key in p.keys: continue
		if key.begins_with("input/"):
			if not "input_actions" in include: continue
			var mapping: Dictionary = ProjectSettings.get_setting(key, {})
			var events: Array = []
			for event: InputEvent in mapping.get("events", []): events.append(input_info(event))
			result.input_actions.append({"name": key.trim_prefix("input/"), "deadzone": mapping.get("deadzone", 0.5), "events": events})
		elif key.begins_with("autoload/"):
			if not "autoload" in include: continue
			var path: String = ProjectSettings.get_setting(key, "")
			result.autoloads.append({"name": key.trim_prefix("autoload/"), "path": path.trim_prefix("*"), "enabled": path.begins_with("*")})
		elif "project" in include and int(prop.usage) & PROPERTY_USAGE_STORAGE:
			result.settings[key] = host.encode(ProjectSettings.get_setting(key))
			result.metadata[key] = {"type": type_string(int(prop.type)), "hint": int(prop.hint), "hint_string": prop.hint_string, "restart_if_changed": bool(int(prop.usage) & PROPERTY_USAGE_RESTART_IF_CHANGED)}
	return result

func mapping_event(spec: Dictionary) -> Dictionary:
	var event: InputEvent
	match str(spec.get("type", "")):
		"key":
			var code: int = OS.find_keycode_from_string(str(spec.get("key", "")))
			if code == KEY_NONE: return host.fail("INVALID_KEY", "Unknown input key name.")
			var key := InputEventKey.new()
			if spec.get("physical", false): key.physical_keycode = code
			else: key.keycode = code
			event = key
		"mouse_button":
			var mouse := InputEventMouseButton.new()
			mouse.button_index = int(spec.get("button", 1))
			event = mouse
		"joypad_button":
			var joy := InputEventJoypadButton.new()
			joy.button_index = int(spec.get("button", 0))
			event = joy
		"joypad_motion":
			var joy := InputEventJoypadMotion.new()
			joy.axis = int(spec.get("axis", 0))
			joy.axis_value = float(spec.get("axis_value", 1))
			event = joy
		_: return host.fail("INVALID_EVENT", "Unknown mapping event type.")
	if event is InputEventWithModifiers:
		event.shift_pressed = spec.get("shift", false)
		event.ctrl_pressed = spec.get("ctrl", false)
		event.alt_pressed = spec.get("alt", false)
		event.meta_pressed = spec.get("meta", false)
	return {"event": event}

func apply_settings(values: Dictionary) -> void:
	for key: String in values:
		if values[key] == null: ProjectSettings.clear(key)
		else: ProjectSettings.set_setting(key, values[key])
	InputMap.load_from_project_settings()

func _normalized_settings(source: String) -> String:
	var parsed := ConfigFile.new()
	if parsed.parse(source) != OK: return ""
	var normalized := ConfigFile.new()
	var sections: PackedStringArray = parsed.get_sections()
	sections.sort()
	for section: String in sections:
		var keys: PackedStringArray = parsed.get_section_keys(section)
		keys.sort()
		for key: String in keys: normalized.set_value(section, key, parsed.get_value(section, key))
	return normalized.encode_to_text()

func settings_snapshot() -> Dictionary:
	# Serialize live settings to private metadata, never to the user's project
	# file. Validation must include unsaved autoload/input/compiler settings.
	var target: String = "res://.godot-mcp/project-state.godot"
	if ProjectSettings.save_custom(target) != OK: return host.fail("SETTINGS_UNAVAILABLE", "Cannot capture current project settings.")
	var source: String = FileAccess.get_file_as_string(target)
	DirAccess.remove_absolute(target)
	var disk: String = FileAccess.get_file_as_string("res://project.godot")
	return {"source": source, "revision": source.sha256_text(), "saved": _normalized_settings(source) == _normalized_settings(disk)}

func update_settings(p: Dictionary) -> Dictionary:
	var after: Dictionary = {}
	for key: String in p.get("settings", {}): after[key] = host.decode(p.settings[key])
	for key: String in p.get("remove", []): after[key] = null
	for action: Dictionary in p.get("input_actions", []):
		var name: String = action.get("name", "")
		if name.is_empty() or name.contains("/"): return host.fail("INVALID_NAME", "Input action names must be nonempty and contain no slash.")
		var value: Variant = null
		if not action.get("remove", false):
			var events: Array[InputEvent] = []
			for spec: Dictionary in action.get("events", []):
				var event: Dictionary = mapping_event(spec)
				if event.has("error"): return event
				events.append(event.event)
			value = {"deadzone": float(action.get("deadzone", 0.5)), "events": events}
		after["input/" + name] = value
	for autoload: Dictionary in p.get("autoloads", []):
		var name: String = autoload.get("name", "")
		if not name.is_valid_identifier() or ClassDB.class_exists(name): return host.fail("INVALID_NAME", "Autoload name must be an identifier that does not shadow an engine class.")
		var value: Variant = null
		if not autoload.get("remove", false):
			var path: String = autoload.get("path", "")
			if not FileAccess.file_exists(path) or path.get_extension() not in ["gd", "tscn", "scn"]: return host.fail("INVALID_AUTOLOAD", "Autoload path must be an existing script or scene.")
			value = ("*" if autoload.get("enabled", true) else "") + path
		after["autoload/" + name] = value
	if after.is_empty(): return host.fail("EMPTY_EDIT", "Provide settings to change.")
	var before: Dictionary = {}
	var restart: bool = false
	for key: String in after:
		if key in ["autoload/GodotMCPRuntime", "editor_plugins/enabled"]: return host.fail("RESERVED_SETTING", "Plugin connectivity settings are managed by installation and the editor.")
		before[key] = ProjectSettings.get_setting(key) if ProjectSettings.has_setting(key) else null
		var info: Dictionary = host.property_info(ProjectSettings, key)
		if not info.is_empty() and after[key] != null and not key.begins_with("input/") and not key.begins_with("autoload/"):
			var error: String = host.property_error(ProjectSettings, {key: p.get("settings", {}).get(key, after[key])})
			if not error.is_empty(): return host.fail("INVALID_SETTING", error)
		if key.begins_with("autoload/") or bool(int(info.get("usage", 0)) & PROPERTY_USAGE_RESTART_IF_CHANGED): restart = true
	host.begin_edit("Update project settings", ProjectSettings)
	host.get_undo_redo().add_do_method(self, "apply_settings", after)
	host.get_undo_redo().add_undo_method(self, "apply_settings", before)
	var result: Dictionary = host.finish_edit(ProjectSettings, "Update project settings")
	result.applied = host.encode(after)
	result.save_uri = "res://project.godot"
	result.restart_required = restart or EditorInterface.is_playing_scene()
	return result

func get_export_presets(p: Dictionary) -> Dictionary:
	var config := ConfigFile.new()
	var error: Error = config.load("res://export_presets.cfg")
	if error == ERR_FILE_NOT_FOUND: return {"presets": [], "reason": "Create an export preset in Project > Export."}
	if error != OK: return host.fail("INVALID_PRESETS", error_string(error))
	var template_directory: String = EditorInterface.get_editor_paths().get_data_dir().path_join("export_templates").path_join(host.Version.ENGINE + ".stable")
	var names: Dictionary = {"Linux": "linux_release.x86_64", "Linux/X11": "linux_release.x86_64", "Windows Desktop": "windows_release_x86_64.exe", "macOS": "macos.zip", "Web": "web_release.zip", "Android": "android_release.apk", "iOS": "ios.zip"}
	var results: Array = []
	for section: String in config.get_sections():
		if not section.begins_with("preset.") or section.contains("/"): continue
		var name: String = config.get_value(section, "name", "")
		var platform: String = config.get_value(section, "platform", "")
		if p.has("preset") and p.preset != name: continue
		if p.has("platform") and p.platform != platform: continue
		var custom: String = config.get_value(section + "/options", "custom_template/release", "")
		var template: String = ProjectSettings.globalize_path(custom) if not custom.is_empty() else template_directory.path_join(names.get(platform, "__unknown__"))
		results.append({"name": name, "platform": platform, "runnable": config.get_value(section, "runnable", false), "export_path": config.get_value(section, "export_path", ""), "template": template, "template_available": FileAccess.file_exists(template), "readiness_note": "Platform SDK/signing requirements are validated by export; pack exports do not require an executable template."})
	return {"presets": results, "template_directory": template_directory}

func local_file(uri: String) -> String:
	if not uri.begins_with("file:///"): return ""
	var path: String = uri.trim_prefix("file://").uri_decode()
	if OS.get_name() == "Windows" and path.length() >= 3 and path[2] == ":": path = path.substr(1)
	return path if path.is_absolute_path() else ""

func export_build(p: Dictionary) -> Dictionary:
	var preset: String = p.get("preset", "")
	var found: Dictionary = get_export_presets({"preset": preset})
	if found.has("error"): return found
	if found.presets.is_empty(): return host.fail("PRESET_NOT_FOUND", "Export preset does not exist.")
	var output: String = local_file(p.get("output", ""))
	if output.is_empty(): return host.fail("INVALID_PATH", "Export output must be an absolute local file URI.")
	if FileAccess.file_exists(output): return host.fail("ALREADY_EXISTS", "Choose a new output path; existing builds are not overwritten.")
	if has_unsaved_documents(): return host.fail("UNSAVED_DOCUMENTS", "Save documents before exporting.")
	var error: Error = DirAccess.make_dir_recursive_absolute(output.get_base_dir())
	if error != OK: return host.fail("OUTPUT_UNWRITABLE", error_string(error))
	var mode: String = "--export-pack" if output.get_extension() in ["pck", "zip"] else ("--export-debug" if p.get("debug", false) else "--export-release")
	var args := PackedStringArray(["--headless", "--path", ProjectSettings.globalize_path("res://"), mode, preset, output])
	var process: Dictionary = OS.execute_with_pipe(OS.get_executable_path(), args, false)
	if process.is_empty(): return host.fail("EXPORT_FAILED", "Could not launch Godot CLI.")
	var stdout: FileAccess = process.stdio
	var stderr: FileAccess = process.stderr
	var deadline: int = Time.get_ticks_msec() + int(p.get("timeout_ms", 120000))
	var collected := ProcessOutput.new()
	while OS.is_process_running(int(process.pid)) and Time.get_ticks_msec() < deadline:
		collected.append("stdout", stdout.get_buffer(65536))
		collected.append("stderr", stderr.get_buffer(65536))
		await host.get_tree().process_frame
	if OS.is_process_running(int(process.pid)):
		OS.kill(int(process.pid))
		stdout.close()
		stderr.close()
		var timeout_output: Dictionary = collected.result()
		return host.fail("EXPORT_TIMEOUT", "Godot export exceeded the requested timeout.", {"log": timeout_output.stdout + timeout_output.stderr, "output_truncated": timeout_output.truncated})
	for stream: String in ["stdout", "stderr"]:
		var pipe: FileAccess = stdout if stream == "stdout" else stderr
		var bytes: PackedByteArray = pipe.get_buffer(65536)
		while not bytes.is_empty():
			collected.append(stream, bytes)
			bytes = pipe.get_buffer(65536)
	stdout.close()
	stderr.close()
	var output_info: Dictionary = collected.result()
	var code: int = OS.get_process_exit_code(int(process.pid))
	if code != 0 or not FileAccess.file_exists(output): return host.fail("EXPORT_FAILED", "Godot did not produce a successful export.", {"exit_code": code, "log": output_info.stdout + output_info.stderr, "output_truncated": output_info.truncated})
	return {"output": p.output, "exit_code": code, "sha256": FileAccess.get_sha256(output), "bytes": FileAccess.open(output, FileAccess.READ).get_length(), "exported": true, "execution_verified": false, "log": output_info.stdout + output_info.stderr, "output_truncated": output_info.truncated}

func writable_asset(path: String) -> bool:
	return path.begins_with("res://") and host.paths_safe(path) and not path.begins_with("res://.") and not path.begins_with("res://addons/godot_mcp/") and path not in ["res://project.godot", "res://export_presets.cfg", "res://export_credentials.cfg"]

func snapshot(paths: Array) -> Dictionary:
	return FileJournal.snapshot(paths)

func has_unsaved_documents() -> bool:
	return not EditorInterface.get_unsaved_scenes().is_empty() or not EditorInterface.get_script_editor().get_unsaved_files().is_empty() or not host.documents.store.dirty_uris().is_empty()

func snapshot_matches(files: Dictionary) -> bool:
	if has_unsaved_documents(): return false
	return FileJournal.matches(files)

func write_files(files: Dictionary, renames: Dictionary = {}) -> bool:
	var open_scenes: PackedStringArray = EditorInterface.get_open_scenes()
	var active_root := EditorInterface.get_edited_scene_root()
	var active_scene: String = active_root.scene_file_path if active_root else ""
	for from: String in renames:
		if from in open_scenes:
			EditorInterface.open_scene_from_path(from)
			EditorInterface.close_scene()
		EditorInterface.get_script_editor().close_file(from)
	for path: String in files:
		if files[path] == null and FileAccess.file_exists(path):
			if DirAccess.remove_absolute(path) != OK: return false
	for path: String in files:
		if files[path] == null: continue
		if DirAccess.make_dir_recursive_absolute(path.get_base_dir()) != OK: return false
		var file := FileAccess.open(path, FileAccess.WRITE)
		if not file: return false
		file.store_buffer(files[path])
		var write_error: Error = file.get_error()
		file.close()
		if write_error != OK: return false
	for from: String in renames:
		if host.resources.has(from):
			var resource: Resource = host.resources[from]
			resource.take_over_path(renames[from])
			host.resources.erase(from)
			host.register_resource(resource)
		host.documents.move_state(from, renames[from])
	EditorInterface.get_resource_filesystem().scan()
	for uri: String in open_scenes:
		var target: String = renames.get(uri, uri)
		if not FileAccess.file_exists(target): continue
		if renames.has(uri): EditorInterface.open_scene_from_path(target)
		elif files.has(uri): EditorInterface.reload_scene_from_path(uri)
	var active_target: String = renames.get(active_scene, active_scene)
	if not active_target.is_empty() and FileAccess.file_exists(active_target): EditorInterface.open_scene_from_path(active_target)
	EditorInterface.get_script_editor().reload_open_files()
	return true

func wait_import(timeout_ms: int = 30000) -> bool:
	var fs := EditorInterface.get_resource_filesystem()
	await host.get_tree().process_frame
	var deadline: int = Time.get_ticks_msec() + timeout_ms
	var quiet_since: int = Time.get_ticks_msec()
	while Time.get_ticks_msec() < deadline:
		if fs.is_scanning() or fs.is_importing(): quiet_since = Time.get_ticks_msec()
		elif Time.get_ticks_msec() - quiet_since >= 250: return true
		await host.get_tree().process_frame
	return false

func record_files(before: Dictionary, after: Dictionary, label: String, renames: Dictionary = {}) -> Dictionary:
	var inverse: Dictionary = {}
	for key: String in renames: inverse[renames[key]] = key
	host.begin_edit(label, ProjectSettings)
	host.get_undo_redo().add_do_method(self, "write_files", after, renames)
	host.get_undo_redo().add_undo_method(self, "write_files", before, inverse)
	return host.finish_edit(ProjectSettings, label, [{"check": snapshot_matches.bind(after)}], false)

func import_assets(p: Dictionary) -> Dictionary:
	return await imports.start(p)

func project_files() -> Array[String]:
	var pending: Array[String] = ["res://"]
	var files: Array[String] = []
	while not pending.is_empty() and files.size() < 20000:
		var path: String = pending.pop_back()
		var dir := DirAccess.open(path)
		if not dir: continue
		for folder: String in dir.get_directories():
			if not folder.begins_with(".") and not dir.is_link(folder): pending.append(path.path_join(folder))
		for file: String in dir.get_files():
			if not file.begins_with(".") and not dir.is_link(file): files.append(path.path_join(file))
	return files

func relative_path(directory: String, target: String) -> String:
	var base: PackedStringArray = directory.trim_prefix("res://").split("/", false)
	var parts: PackedStringArray = target.trim_prefix("res://").split("/", false)
	var shared: int = 0
	while shared < mini(base.size(), parts.size()) and base[shared] == parts[shared]: shared += 1
	var result := PackedStringArray()
	for _i: int in range(shared, base.size()): result.append("..")
	for i: int in range(shared, parts.size()): result.append(parts[i])
	return "/".join(result)

func rewrite_references(text: String, old_uri: String, new_uri: String, moves: Dictionary) -> String:
	var regex := RegEx.new()
	regex.compile("([\"'])([^\"'\\n]+)\\1")
	var matches: Array[RegExMatch] = regex.search_all(text)
	matches.reverse()
	for match_value: RegExMatch in matches:
		var value: String = match_value.get_string(2)
		var resolved: String = value if value.begins_with("res://") else old_uri.get_base_dir().path_join(value).simplify_path()
		var replacement: String = str(moves.get(resolved, resolved))
		if not moves.has(resolved) and (old_uri == new_uri or not FileAccess.file_exists(resolved)): continue
		if not value.begins_with("res://"): replacement = relative_path(new_uri.get_base_dir(), replacement)
		text = text.substr(0, match_value.get_start(2)) + replacement + text.substr(match_value.get_end(2))
	return text

func move_assets(p: Dictionary) -> Dictionary:
	if not imports.pending().is_empty(): return host.fail("OPERATION_PENDING", "Wait for pending imports before moving project files.", {"operations": imports.pending()})
	if EditorInterface.is_playing_scene(): return host.fail("GAME_RUNNING", "Stop the game before moving its files.")
	if has_unsaved_documents(): return host.fail("UNSAVED_DOCUMENTS", "Save open documents before filesystem moves.")
	var moves: Dictionary = {}
	var destinations: Dictionary = {}
	for move: Dictionary in p.get("moves", []):
		var from: String = move.get("from", "")
		var to: String = move.get("to", "")
		if not writable_asset(from) or not writable_asset(to): return host.fail("INVALID_PATH", "Move only authored project files.")
		if not FileAccess.file_exists(from): return host.fail("FILE_NOT_FOUND", "Move source does not exist.")
		if FileAccess.file_exists(to) or moves.has(from) or destinations.has(to): return host.fail("DESTINATION_CONFLICT", "Move sources/destinations must be unique; destinations must not exist.")
		moves[from] = to
		destinations[to] = true
	var before: Dictionary = {}
	var after: Dictionary = {}
	var rewritten: Array = []
	var unresolved: Array = []
	var files: Array[String] = project_files()
	for path: String in files:
		if path.begins_with("res://addons/godot_mcp/"): continue
		if path.get_extension() in ["res", "scn"]:
			for dep: String in ResourceLoader.get_dependencies(path):
				for from: String in moves:
					if dep == from or dep.ends_with("::" + from): return host.fail("BINARY_DEPENDENCY", "Resave this binary dependent as a text resource/scene before moving its dependency.", {"uri": path, "dependency": from})
		if path.get_extension() not in ["gd", "gdshader", "tscn", "tres", "godot", "cfg", "import"]: continue
		var file := FileAccess.open(path, FileAccess.READ)
		if not file or file.get_length() > 4 * 1024 * 1024: continue
		var text: String = file.get_as_text()
		var target: String = moves.get(path, path)
		var replaced: String = rewrite_references(text, path, target, moves)
		if replaced != text:
			before[path] = text.to_utf8_buffer()
			after[target] = replaced.to_utf8_buffer()
			rewritten.append(target)
		for from: String in moves:
			if text.contains(from.get_file().get_basename()) and path.ends_with(".gd"):
				unresolved.append({"uri": target, "note": "Review dynamically assembled paths; exact path literals were reconciled."})
	for from: String in moves:
		var to: String = moves[from]
		for suffix: String in ["", ".uid", ".import"]:
			var source: String = from + suffix
			var target: String = to + suffix
			before[source] = FileAccess.get_file_as_bytes(source) if FileAccess.file_exists(source) else null
			before[target] = null
			after[source] = null
			if before[source] != null and not after.has(target):
				var bytes: PackedByteArray = before[source]
				if suffix == ".import": bytes = rewrite_references(bytes.get_string_from_utf8(), source, target, moves).to_utf8_buffer()
				after[target] = bytes
	if not write_files(after, moves):
		write_files(before)
		return host.fail("MOVE_FAILED", "Could not apply file moves; originals were restored.")
	await wait_import()
	# Reimports can update their generated sidecars. Guard the actual final bytes.
	var actual: Dictionary = snapshot(after.keys())
	var result: Dictionary = record_files(before, actual, "Move assets", moves)
	result.saved = true
	result.moves = p.moves
	result.updated_references = rewritten
	result.review = unresolved
	return result
