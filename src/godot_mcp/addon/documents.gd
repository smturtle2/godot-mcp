@tool
extends RefCounted
## Live script buffers and explicit persistence; no broad save-all side effects.
var host: EditorPlugin
var states: Dictionary = {}
var code_diagnostics: Dictionary = {}
var owned_breakpoints: Dictionary = {}

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func handles(method: String) -> bool:
	return method in ["find_assets", "read_script", "create_script", "edit_script", "save_documents", "update_signals", "get_diagnostics"]

func dispatch(method: String, p: Dictionary) -> Dictionary:
	match method:
		"find_assets": return find_assets(p)
		"read_script": return read_script(p)
		"create_script": return await create_script(p)
		"edit_script": return await edit_script(p)
		"save_documents": return await save_documents(p)
		"update_signals": return update_signals(p)
		"get_diagnostics": return await get_diagnostics(p)
	return host.fail("UNKNOWN_TOOL", method)

func script_buffer(uri: String) -> TextEdit:
	var editor := EditorInterface.get_script_editor()
	var script: Script
	for candidate: Script in editor.get_open_scripts():
		if candidate.resource_path == uri:
			script = candidate
			break
	if not script: return null
	var previous: Script = editor.get_current_script()
	if previous != script: EditorInterface.edit_script(script, -1, 0, false)
	var base: ScriptEditorBase = editor.get_current_editor()
	var text: TextEdit = base.get_base_editor() as TextEdit if base and editor.get_current_script() == script else null
	if previous and previous != script: EditorInterface.edit_script(previous, -1, 0, false)
	return text

func source_info(uri: String) -> Dictionary:
	if not uri.begins_with("res://") or uri.get_extension() not in ["gd", "gdshader"]:
		return host.fail("UNSUPPORTED_LANGUAGE", "Use a .gd or .gdshader project file.")
	if not FileAccess.file_exists(uri): return host.fail("FILE_NOT_FOUND", "Source file does not exist.")
	var disk: String = FileAccess.get_file_as_string(uri)
	var source: String = disk
	var buffer: TextEdit = script_buffer(uri) if uri.ends_with(".gd") else null
	if buffer:
		source = buffer.text
	elif states.has(uri) and states[uri].dirty:
		source = states[uri].source
	elif uri.ends_with(".gdshader"):
		var shader: Shader = host.resource_uri(uri) as Shader
		if shader: source = shader.code
	return {"uri": uri, "source": source, "revision": source.sha256_text(), "disk_revision": disk.sha256_text(), "unsaved": source != disk, "buffer": "editor" if buffer else ("resource" if source != disk else "disk"), "external_change": source != disk and states.has(uri) and states[uri].get("disk_revision", disk.sha256_text()) != disk.sha256_text() and states[uri].dirty}

func symbols(source: String) -> Array:
	var regex := RegEx.new()
	regex.compile("(?m)^(?:static[ \\t]+)?(?:func|class_name|class|signal|var|const)[ \\t]+([A-Za-z_][A-Za-z0-9_]*)")
	var results: Array = []
	for match_value: RegExMatch in regex.search_all(source):
		var offset: int = match_value.get_start(1)
		var prefix: String = source.substr(0, offset)
		results.append({"name": match_value.get_string(1), "line": prefix.count("\n") + 1, "column": offset - prefix.rfind("\n"), "offset": offset})
	return results

func offset(source: String, position: Dictionary) -> int:
	var lines: PackedStringArray = source.split("\n")
	var line: int = int(position.get("line", 0)) - 1
	var column: int = int(position.get("column", 0)) - 1
	if line < 0 or line >= lines.size() or column < 0 or column > lines[line].length(): return -1
	var index: int = column
	for i: int in line: index += lines[i].length() + 1
	return index

func read_script(p: Dictionary) -> Dictionary:
	var result: Dictionary = source_info(str(p.get("uri", "")))
	if result.has("error"): return result
	result.symbols = symbols(result.source)
	if p.has("range"):
		var start: int = offset(result.source, p.range.start)
		var end: int = offset(result.source, p.range.end)
		if start < 0 or end < start: return host.fail("INVALID_RANGE", "Source range is outside the current document.")
		result.source = result.source.substr(start, end - start)
		result.range = p.range
	if p.has("symbol"):
		var selected: Array = result.symbols.filter(func(item: Dictionary) -> bool: return item.name == p.symbol)
		if selected.is_empty(): return host.fail("SYMBOL_NOT_FOUND", "No matching top-level symbol.")
		result.symbols = selected
	return result

func set_source(uri: String, source: String) -> void:
	var before_disk: String = FileAccess.get_file_as_string(uri)
	var resource: Resource = host.resource_uri(uri)
	if resource is Script:
		var buffer: TextEdit = script_buffer(uri)
		if buffer and buffer.text != source:
			buffer.begin_complex_operation()
			buffer.select_all()
			buffer.insert_text_at_caret(source)
			buffer.deselect()
			buffer.end_complex_operation()
		resource.source_code = source
		resource.reload(true)
	elif resource is Shader:
		resource.code = source
		resource.get_rid()
	states[uri] = {"source": source, "disk_revision": before_disk.sha256_text(), "dirty": source != before_disk}
	if resource:
		EditorInterface.set_object_edited(resource, source != before_disk)

func source_matches(uri: String, revision: String) -> bool:
	var info: Dictionary = source_info(uri)
	return not info.has("error") and info.revision == revision

func validate_source(uri: String, resource: Resource, source: String) -> Dictionary:
	var cursor: int = host.logs.read().cursor
	var error: Error = OK
	if resource is Script:
		resource.source_code = source
		error = resource.reload(true)
	elif resource is Shader:
		resource.code = source
		resource.get_rid()
	var entries: Array = host.logs.read(cursor).entries
	if error != OK and entries.is_empty():
		entries.append({"kind": "error", "uri": uri, "message": error_string(error), "line": 0})
	var value: Dictionary = {"uri": uri, "revision": source.sha256_text(), "valid": error == OK, "entries": entries}
	code_diagnostics[uri] = value
	return value

func create_script(p: Dictionary) -> Dictionary:
	var uri: String = p.get("uri", "")
	if not uri.begins_with("res://") or uri.get_extension() not in ["gd", "gdshader"]: return host.fail("UNSUPPORTED_LANGUAGE", "Use .gd or .gdshader.")
	if FileAccess.file_exists(uri): return host.fail("ALREADY_EXISTS", "Source file already exists.")
	var source: String = p.get("source", "")
	var resource: Resource = GDScript.new() if uri.ends_with(".gd") else Shader.new()
	var nodes: Array[Node] = []
	var root: Node
	if resource is Shader and not p.get("attach_to", []).is_empty(): return host.fail("INVALID_ATTACHMENT", "Attach shaders to a ShaderMaterial with material=.")
	for ref: Dictionary in p.get("attach_to", []):
		var node: Node = host.resolve_node(ref)
		if not node: return host.fail("NODE_NOT_FOUND", "Attachment target does not exist.")
		var scene: Node = host.scene_root(ref.scene)
		if root and root != scene: return host.fail("CROSS_SCENE", "Attach to one scene per batch.")
		root = scene
		nodes.append(node)
	var material: ShaderMaterial
	if p.has("material"):
		if resource is Script: return host.fail("INVALID_ATTACHMENT", "material is only valid for shader source.")
		material = host.resolve_resource(p.material) as ShaderMaterial
		if not material: return host.fail("INVALID_RESOURCE", "material must resolve to ShaderMaterial.")
	var error: Error = DirAccess.make_dir_recursive_absolute(uri.get_base_dir())
	if error != OK: return host.fail("SAVE_FAILED", error_string(error))
	if resource is Script: resource.source_code = source
	else: resource.code = source
	error = ResourceSaver.save(resource, uri, ResourceSaver.FLAG_CHANGE_PATH)
	if error != OK: return host.fail("SAVE_FAILED", error_string(error))
	host.register_resource(resource)
	var diagnostics: Dictionary = validate_source(uri, resource, source)
	var changes: Array[Dictionary] = []
	var attachment_errors: Array = []
	for node: Node in nodes:
		if resource is Script and (not diagnostics.valid or not node.is_class(resource.get_instance_base_type())):
			attachment_errors.append({"node": host.node_ref(node), "message": "Script does not compile or its base type is incompatible."})
		else:
			changes.append({"object": node, "property": "script", "before": node.get_script(), "after": resource})
	if material: changes.append({"object": material, "property": "shader", "before": material.shader, "after": resource})
	var result: Dictionary = {"uri": uri, "revision": source.sha256_text(), "saved": true, "diagnostics": diagnostics, "attached": [], "attachment_errors": attachment_errors}
	if not changes.is_empty():
		var edit: Dictionary = host.commit_changes(changes, root if root else material, "Attach source")
		result.edit_id = edit.get("edit_id")
		result.attachments_saved = false
		for change: Dictionary in changes:
			result.attached.append(host.node_ref(change.object) if change.object is Node else {"resource": host.register_resource(change.object), "property": change.property})
	states[uri] = {"source": source, "disk_revision": source.sha256_text(), "dirty": false}
	EditorInterface.get_resource_filesystem().update_file(uri)
	await host.get_tree().process_frame
	return result

func edit_script(p: Dictionary) -> Dictionary:
	var uri: String = p.get("uri", "")
	var info: Dictionary = source_info(uri)
	if info.has("error"): return info
	if p.get("if_revision", "") != info.revision: return host.fail("REVISION_CONFLICT", "Source changed; read_script again before editing.", {"current_revision": info.revision})
	if info.external_change: return host.fail("EXTERNAL_CHANGE", "The disk file changed while this document had unsaved edits.")
	var ranges: Array[Dictionary] = []
	for edit: Dictionary in p.get("edits", []):
		var start: int = offset(info.source, edit.range.start)
		var end: int = offset(info.source, edit.range.end)
		if start < 0 or end < start: return host.fail("INVALID_RANGE", "Edit range is outside the current document.")
		ranges.append({"start": start, "end": end, "text": edit.text})
	ranges.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.start < b.start)
	for i: int in range(1, ranges.size()):
		if ranges[i].start < ranges[i - 1].end or ranges[i].start == ranges[i - 1].start: return host.fail("OVERLAPPING_EDITS", "Combine overlapping edits or insertions at the same position.")
	var source: String = info.source
	ranges.reverse()
	for edit: Dictionary in ranges: source = source.substr(0, edit.start) + str(edit.text) + source.substr(edit.end)
	var resource: Resource = host.resource_uri(uri)
	if not resource: return host.fail("SOURCE_UNAVAILABLE", "Cannot load source resource.")
	host.begin_edit("Edit source", resource)
	host.get_undo_redo().add_do_method(self, "set_source", uri, source)
	host.get_undo_redo().add_undo_method(self, "set_source", uri, info.source)
	var guards: Array = [{"check": source_matches.bind(uri, source.sha256_text())}]
	var result: Dictionary = host.finish_edit(resource, "Edit source", guards)
	await host.get_tree().process_frame
	result.uri = uri
	result.revision = source.sha256_text()
	result.diagnostics = validate_source(uri, resource, source)
	result.runtime_application = "eligible_for_gdscript_hot_reload" if resource is GDScript and EditorInterface.is_playing_scene() else "not_running_or_shader_resource"
	return result

func save_documents(p: Dictionary) -> Dictionary:
	var saved: Array = []
	var failed: Array = []
	var original_root := EditorInterface.get_edited_scene_root()
	var original_scene: String = original_root.scene_file_path if original_root else ""
	for uri: String in p.get("uris", []):
		var target: String = str(p.get("save_as", {}).get(uri, uri))
		if not target.begins_with("res://") or not host.paths_safe(target):
			failed.append({"uri": uri, "error": "A res:// save_as path is required for an in-memory resource."})
			continue
		if target != uri and FileAccess.file_exists(target):
			failed.append({"uri": uri, "error": "save_as destination already exists."})
			continue
		var error: Error = OK
		if uri == "res://project.godot":
			if target != uri: error = ERR_INVALID_PARAMETER
			else: error = ProjectSettings.save()
		elif uri.ends_with(".tscn"):
			var root: Node = host.scene_root(uri)
			if not root:
				error = ERR_FILE_NOT_FOUND
			else:
				EditorInterface.open_scene_from_path(uri)
				if target == uri: error = EditorInterface.save_scene()
				else:
					DirAccess.make_dir_recursive_absolute(target.get_base_dir())
					EditorInterface.save_scene_as(target, false)
					error = OK if root.scene_file_path == target and FileAccess.file_exists(target) else ERR_FILE_CANT_WRITE
		elif uri.get_extension() in ["gd", "gdshader"]:
			var info: Dictionary = source_info(uri)
			if info.has("error") or info.get("external_change", false):
				failed.append({"uri": uri, "error": "Source is missing or disk changes conflict with unsaved edits."})
				continue
			var resource: Resource = host.resource_uri(uri)
			if resource is Script: resource.source_code = info.source
			elif resource is Shader: resource.code = info.source
			if resource:
				DirAccess.make_dir_recursive_absolute(target.get_base_dir())
				error = ResourceSaver.save(resource, target, ResourceSaver.FLAG_CHANGE_PATH)
				if error == OK:
					var buffer: TextEdit = script_buffer(uri)
					if buffer: buffer.tag_saved_version()
					states.erase(uri)
					states[target] = {"source": info.source, "disk_revision": str(info.source).sha256_text(), "dirty": false}
					EditorInterface.set_object_edited(resource, false)
			else: error = ERR_FILE_UNRECOGNIZED
		else:
			var resource: Resource = host.resource_uri(uri)
			if not resource: error = ERR_FILE_NOT_FOUND
			elif target.get_extension() not in ["tres", "res"]: error = ERR_INVALID_PARAMETER
			else:
				DirAccess.make_dir_recursive_absolute(target.get_base_dir())
				error = ResourceSaver.save(resource, target, ResourceSaver.FLAG_CHANGE_PATH)
				if error == OK:
					host.register_resource(resource)
					EditorInterface.set_object_edited(resource, false)
		if error == OK:
			saved.append({"uri": uri, "saved_as": target})
			EditorInterface.get_resource_filesystem().update_file(target)
		else:
			failed.append({"uri": uri, "error": error_string(error)})
	if not original_scene.is_empty() and FileAccess.file_exists(original_scene): EditorInterface.open_scene_from_path(original_scene)
	await host.get_tree().process_frame
	return {"saved": saved, "failed": failed, "complete": failed.is_empty()}

func find_assets(p: Dictionary) -> Dictionary:
	var scope: String = p.get("scope", "res://")
	if not scope.begins_with("res://") or not host.paths_safe(scope): return host.fail("INVALID_PATH", "Search scope must remain in the project.")
	var query: String = str(p.get("query", "")).to_lower()
	var mode: String = p.get("mode", "name")
	var limit: int = int(p.get("limit", 100))
	var results: Array = []
	var pending: Array[String] = [scope]
	var visited: int = 0
	while not pending.is_empty() and results.size() < limit and visited < 20000:
		var path: String = pending.pop_back()
		if DirAccess.dir_exists_absolute(path):
			var directory := DirAccess.open(path)
			if not directory: continue
			for folder: String in directory.get_directories():
				if folder.begins_with(".") or directory.is_link(folder): continue
				pending.append(path.path_join(folder))
			for file: String in directory.get_files():
				if not file.begins_with(".") and not directory.is_link(file): pending.append(path.path_join(file))
			continue
		visited += 1
		var type: String = EditorInterface.get_resource_filesystem().get_file_type(path)
		if not p.get("types", []).is_empty() and not type in p.types and not (type == "GDScript" and "Script" in p.types): continue
		if mode == "name":
			if path.to_lower().contains(query): results.append({"uri": path, "type": type})
		elif path.get_extension() in ["gd", "gdshader", "tscn", "tres", "godot", "cfg", "txt", "json"]:
			var file := FileAccess.open(path, FileAccess.READ)
			if not file or file.get_length() > 2 * 1024 * 1024: continue
			var source: String = file.get_as_text()
			if path.get_extension() in ["gd", "gdshader"]:
				var live: Dictionary = source_info(path)
				if not live.has("error"): source = live.source
			if mode == "symbol":
				for symbol: Dictionary in symbols(source):
					if str(symbol.name).to_lower().contains(query):
						symbol.uri = path
						results.append(symbol)
						if results.size() >= limit: break
			else:
				var lines: PackedStringArray = source.split("\n")
				for i: int in lines.size():
					var col: int = lines[i].to_lower().find(query)
					if col >= 0:
						results.append({"uri": path, "line": i + 1, "column": col + 1, "text": lines[i].substr(0, 1000), "type": type})
						if results.size() >= limit: break
	return {"matches": results, "truncated": not pending.is_empty(), "searched_files": visited}

func update_signals(p: Dictionary) -> Dictionary:
	var staged: Array[Dictionary] = []
	var root: Node
	for op: String in ["connect", "disconnect"]:
		for spec: Dictionary in p.get(op, []):
			var from: Node = host.resolve_node(spec.get("from", {}))
			var to: Node = host.resolve_node(spec.get("to", {}))
			if not from or not to: return host.fail("NODE_NOT_FOUND", "Signal endpoints must exist.")
			if spec.from.scene != spec.to.scene: return host.fail("CROSS_SCENE", "Persistent signals must belong to one scene.")
			var scene: Node = host.scene_root(spec.from.scene)
			if root and root != scene: return host.fail("CROSS_SCENE", "Batch signal changes in one document.")
			root = scene
			if not from.has_signal(spec.signal): return host.fail("SIGNAL_NOT_FOUND", "Source signal does not exist.")
			if op == "connect" and not to.has_method(spec.method): return host.fail("HANDLER_MISSING", "Create the receiving method before connecting.", {"required_handler": {"node": spec.to, "method": spec.method}})
			var callable := Callable(to, spec.method).bindv(host.decode(spec.get("binds", [])))
			var connected: bool = from.is_connected(spec.signal, callable)
			staged.append({"op": op, "from": from, "signal": spec.signal, "callable": callable, "connected": connected, "spec": spec})
	if staged.is_empty(): return host.fail("EMPTY_EDIT", "Provide connections or disconnections.")
	host.begin_edit("Update signals", root)
	var undo: EditorUndoRedoManager = host.get_undo_redo()
	for item: Dictionary in staged:
		if item.op == "connect" and not item.connected:
			undo.add_do_method(item.from, "connect", item.signal, item.callable, CONNECT_PERSIST)
			undo.add_undo_method(item.from, "disconnect", item.signal, item.callable)
		elif item.op == "disconnect" and item.connected:
			var flags: int = CONNECT_PERSIST
			for connection: Dictionary in item.from.get_signal_connection_list(item.signal):
				if connection.callable == item.callable: flags = int(connection.flags)
			undo.add_do_method(item.from, "disconnect", item.signal, item.callable)
			undo.add_undo_method(item.from, "connect", item.signal, item.callable, flags)
	var result: Dictionary = host.finish_edit(root, "Update signals")
	result.connections = []
	for item: Dictionary in staged: result.connections.append({"connection": item.spec, "connected": item.from.is_connected(item.signal, item.callable)})
	return result

func get_diagnostics(p: Dictionary) -> Dictionary:
	var source_results: Array = []
	for uri: String in p.get("uris", []):
		var info: Dictionary = source_info(uri)
		if info.has("error"): return info
		if p.has("revision") and p.revision != info.revision: return host.fail("STALE_REVISION", "Diagnostics requested for an old source revision.", {"current_revision": info.revision})
		if not code_diagnostics.has(uri) or code_diagnostics[uri].revision != info.revision:
			var resource: Resource = host.resource_uri(uri)
			if resource: validate_source(uri, resource, info.source)
		if code_diagnostics.has(uri): source_results.append(code_diagnostics[uri])
	var result: Dictionary = host.logs.read(int(p.get("since", 0)), int(p.get("limit", 200)))
	if not p.get("kinds", []).is_empty(): result.entries = result.entries.filter(func(item: Dictionary) -> bool: return item.kind in p.kinds)
	result.sources = source_results
	result.origin = "editor"
	if p.has("run_id"):
		if p.run_id != host.runtime.run_id or not host.runtime.ready: return host.fail("STALE_RUN", "No matching runtime.")
		result.runtime = await host.debugger.request("get_diagnostics", p)
	return result

func breakpoints(p: Dictionary) -> Dictionary:
	var editor := EditorInterface.get_script_editor()
	var existing: Dictionary = {}
	for entry: String in editor.get_breakpoints():
		var colon: int = entry.rfind(":")
		if colon < 0: continue
		var uri: String = entry.substr(0, colon)
		if not existing.has(uri): existing[uri] = []
		existing[uri].append(int(entry.substr(colon + 1)))
	if p.get("read_only", false): return {"all": existing, "owned": owned_breakpoints}
	var desired: Dictionary = owned_breakpoints.duplicate(true)
	if p.get("replace", false): desired.clear()
	for point: Dictionary in p.get("breakpoints", []):
		var uri: String = point.get("uri", "")
		if not uri.ends_with(".gd") or not FileAccess.file_exists(uri): return host.fail("UNSUPPORTED_LANGUAGE", "Breakpoints require an existing .gd file.")
		if not desired.has(uri): desired[uri] = []
		var line: int = int(point.get("line", 0))
		var source: Dictionary = source_info(uri)
		if line < 1 or line > str(source.get("source", "")).split("\n").size(): return host.fail("INVALID_LINE", "Breakpoint lies outside source.")
		if point.get("enabled", true):
			if not line in existing.get(uri, []) or line in owned_breakpoints.get(uri, []):
				if not line in desired[uri]: desired[uri].append(line)
		else: desired[uri].erase(line)
	var combined: Dictionary = existing.duplicate(true)
	for uri: String in owned_breakpoints:
		if not combined.has(uri): combined[uri] = []
		for line: int in owned_breakpoints[uri]: combined[uri].erase(line)
	for uri: String in desired:
		if not combined.has(uri): combined[uri] = []
		for line: int in desired[uri]:
			if not line in combined[uri]: combined[uri].append(line)
	var original: Script = editor.get_current_script()
	for uri: String in combined:
		var script: Script = host.resource_uri(uri) as Script
		if not script: continue
		EditorInterface.edit_script(script, -1, 0, false)
		var buffer: CodeEdit = script_buffer(uri) as CodeEdit
		if not buffer: continue
		for line: int in buffer.get_breakpointed_lines(): buffer.set_line_as_breakpoint(line, false)
		for line: int in combined[uri]: buffer.set_line_as_breakpoint(line - 1, true)
	if original: EditorInterface.edit_script(original, -1, 0, false)
	owned_breakpoints = desired
	return {"all": combined, "owned": desired}
