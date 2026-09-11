@tool
extends RefCounted
## Source editing and explicit persistence, including Godot's linked-resource saves.
var host: EditorPlugin
const SourceStore = preload("res://addons/godot_mcp/source_store.gd")
const SourceValidation = preload("res://addons/godot_mcp/source_validation.gd")
const LogBuffer = preload("res://addons/godot_mcp/log_buffer.gd")
var store: RefCounted
var validator: RefCounted
var owned_breakpoints: Dictionary = {}

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host
	store = SourceStore.new(host)
	validator = SourceValidation.new(host)

func handles(method: String) -> bool:
	return method in ["find_assets", "read_script", "create_script", "edit_script", "apply_script_changes", "save_documents", "update_signals", "get_diagnostics"]

func dispatch(method: String, p: Dictionary) -> Dictionary:
	match method:
		"find_assets": return find_assets(p)
		"read_script": return read_script(p)
		"create_script": return await create_script(p)
		"edit_script": return await edit_script(p)
		"apply_script_changes": return await apply_script_changes(p)
		"save_documents": return await save_documents(p)
		"update_signals": return update_signals(p)
		"get_diagnostics": return await get_diagnostics(p)
	return host.fail("UNKNOWN_TOOL", method)

func script_buffer(uri: String) -> TextEdit:
	return store.script_buffer(uri)

func source_info(uri: String) -> Dictionary:
	return store.source_info(uri)

func dirty_uris() -> Array:
	return store.dirty_uris()

func move_state(from: String, to: String) -> void:
	store.move_state(from, to)

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

func validate_sources(uris: Array) -> Dictionary:
	var overlays: Dictionary = store.overlays()
	var conflicts: Array = store.conflicts()
	if not conflicts.is_empty(): return host.fail("EXTERNAL_CHANGE", "Resolve source buffer and disk conflicts before validation.", {"conflicts": conflicts})
	var before: Dictionary = overlays.duplicate(true)
	var revisions: Dictionary = {}
	for uri: String in uris:
		var info: Dictionary = source_info(uri)
		if info.has("error"): return info
		if info.external_change: return host.fail("EXTERNAL_CHANGE", "Resolve conflicting disk and unsaved source changes before validation.", {"uri": uri})
		overlays[uri] = info.source
		revisions[uri] = info.revision
	var result: Dictionary = await validator.check(uris, overlays, revisions)
	var stale: bool = store.overlays() != before
	for uri: String in uris:
		if not store.source_matches(uri, revisions[uri]): stale = true
	if stale:
		for item: Dictionary in result.sources:
			item.state = "pending"
			item.valid = null
			item.entries = [{"kind": "warning", "uri": item.uri, "line": 0, "message": "Sources changed during validation; request current diagnostics again."}]
	return result

func validate_source(uri: String, _resource: Resource, _source: String) -> Dictionary:
	var result: Dictionary = await validate_sources([uri])
	if result.has("error"):
		return {"uri": uri, "revision": _source.sha256_text(), "state": "unavailable", "valid": null, "scope": "snapshot", "entries": [{"kind": "error", "uri": uri, "line": 0, "message": result.error.message}]}
	return result.sources[0]

func document_state(uri: String) -> Dictionary:
	var info: Dictionary = source_info(uri)
	if info.has("error"): return {"uri": uri, "state": "unavailable"}
	return {"uri": uri, "state": "saved" if not info.unsaved else ("modified" if info.exists_on_disk else "draft"), "revision": info.revision, "disk_revision": info.disk_revision, "base_disk_revision": info.base_disk_revision, "baseline_known": info.baseline_known, "conflict": info.conflict, "saved": not info.unsaved}

func create_script(p: Dictionary) -> Dictionary:
	var uri: String = p.get("uri", "")
	if not uri.begins_with("res://") or uri.get_extension() not in ["gd", "gdshader"]: return host.fail("UNSUPPORTED_LANGUAGE", "Use .gd or .gdshader.")
	if not source_info(uri).has("error"): return host.fail("ALREADY_EXISTS", "Source already exists; use read_script and edit_script to modify it.")
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
	resource.resource_path = uri
	error = ResourceSaver.save(resource, uri, ResourceSaver.FLAG_CHANGE_PATH)
	if error != OK: return host.fail("SAVE_FAILED", error_string(error))
	host.register_resource(resource)
	store.mark_saved(uri)
	var diagnostics: Dictionary = await validate_source(uri, resource, source)
	var live_valid: bool = diagnostics.get("valid") == true
	if resource is Script and live_valid: live_valid = resource.reload(true) == OK
	var changes: Array[Dictionary] = []
	var attachment_errors: Array = []
	for node: Node in nodes:
		if resource is Script and not live_valid:
			attachment_errors.append({"node": host.node_ref(node), "code": "COMPILE_FAILED" if diagnostics.get("valid") != true else "LIVE_RELOAD_FAILED", "message": "Validation must succeed and the live script must reload before attaching.", "retry": {"tool": "update_nodes", "arguments": {"changes": [{"node": host.node_ref(node), "set": {"script": {"$type": "Resource", "uri": uri}}}]}}})
		else:
			var node_plan: Dictionary = host.plan_property_changes(node, {"script": {"$type": "Resource", "uri": uri}})
			if node_plan.has("error"):
				attachment_errors.append({"node": host.node_ref(node), "code": "INCOMPATIBLE_BASE", "message": str(node_plan.error.get("message", "Script cannot be attached.")), "retry": {"tool": "update_nodes", "arguments": {"changes": [{"node": host.node_ref(node), "set": {"script": {"$type": "Resource", "uri": uri}}}]}}})
			else:
				changes.append_array(node_plan.get("changes", []))
	if material and diagnostics.get("valid") == true:
		var material_plan: Dictionary = host.plan_property_changes(material, {"shader": {"$type": "Resource", "uri": uri}})
		if material_plan.has("error"):
			attachment_errors.append({"resource": host.register_resource(material), "code": "INCOMPATIBLE_SHADER", "message": str(material_plan.error.get("message", "Shader cannot be attached to this material.")), "retry": {"tool": "update_resource", "arguments": {"target": {"uri": host.register_resource(material)}, "scope": "shared", "set": {"shader": {"$type": "Resource", "uri": uri}}}}})
		else:
			changes.append_array(material_plan.get("changes", []))
	elif material:
		attachment_errors.append({"resource": host.register_resource(material), "code": "COMPILE_FAILED", "message": "Shader was saved; attachment skipped because validation did not pass.", "retry": {"tool": "update_resource", "arguments": {"target": {"uri": host.register_resource(material)}, "scope": "shared", "set": {"shader": {"$type": "Resource", "uri": uri}}}}})
	var result: Dictionary = {"uri": uri, "revision": source.sha256_text(), "saved": true, "diagnostics": diagnostics, "attached": [], "attachment_errors": attachment_errors}
	if not changes.is_empty():
		var edit: Dictionary = host.commit_changes(changes, root if root else material, "Attach source")
		result.edit_id = edit.get("edit_id")
		result.attachments_saved = false
		for change: Dictionary in changes:
			result.attached.append(host.node_ref(change.object) if change.object is Node else {"resource": host.register_resource(change.object), "property": change.property})
	result.live_reload = "succeeded" if live_valid else "failed"
	result.status = "completed" if diagnostics.get("valid") == true and live_valid and attachment_errors.is_empty() else "partial"
	result.summary = "Source file saved; validation and requested attachments completed." if result.status == "completed" else "Source file remains saved; validation, live reload, or requested attachment did not complete. Edit the existing file instead of recreating it."
	result.document = document_state(uri)
	result.undo = {"edit_id": result.get("edit_id"), "scope": ["attachments"] if result.has("edit_id") else [], "retained_files": [uri]}
	result.pending_save = [root.scene_file_path] if root and result.has("edit_id") else []
	if material and result.has("edit_id"): result.pending_save.append(host.register_resource(material))
	EditorInterface.get_resource_filesystem().update_file(uri)
	await host.get_tree().process_frame
	return result

func edited_source(info: Dictionary, p: Dictionary) -> Dictionary:
	if p.has("source"): return {"source": p.source}
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
	return {"source": source}

func edit_script(p: Dictionary) -> Dictionary:
	var changed: Dictionary = p.duplicate(true)
	var result: Dictionary = await apply_script_changes({"changes": [changed], "save": false})
	if result.has("error"): return result
	var document: Dictionary = result.documents[0]
	result.uri = document.uri
	result.revision = document.revision
	result.saved = document.saved
	result.diagnostics = result.validation.sources[0]
	result.runtime_application = "source_updated; running_game_application_not_verified"
	return result

func apply_script_changes(p: Dictionary) -> Dictionary:
	var plans: Array[Dictionary] = []
	var uris: Array = []
	for change: Dictionary in p.get("changes", []):
		var uri: String = change.get("uri", "")
		if not uri.begins_with("res://") or uri.get_extension() not in ["gd", "gdshader"]: return host.fail("UNSUPPORTED_LANGUAGE", "Use .gd or .gdshader sources.")
		if uri in uris: return host.fail("DUPLICATE_DOCUMENT", "Combine changes for each URI into one entry.", {"uri": uri})
		var info: Dictionary = source_info(uri)
		var create: bool = change.get("create", false)
		if create:
			if not info.has("error"): return host.fail("ALREADY_EXISTS", "Source or draft already exists; edit it using its revision.", {"uri": uri})
			info = {"source": "", "revision": "", "unsaved": false}
		else:
			if info.has("error"): return info
			if info.external_change: return host.fail("EXTERNAL_CHANGE", "The disk changed while this source had unsaved edits.", {"uri": uri})
			if change.get("if_revision", "") != info.revision: return host.fail("REVISION_CONFLICT", "Read current source before editing.", {"uri": uri, "current_revision": info.revision})
		var edited: Dictionary = edited_source(info, change)
		if edited.has("error"): return edited
		uris.append(uri)
		plans.append({"uri": uri, "source": edited.source, "before": null if create else info.source, "create": create})
	if plans.is_empty(): return host.fail("EMPTY_EDIT", "Provide at least one source change.")
	# All input/revision checks precede any live source mutation.
	for plan: Dictionary in plans:
		if plan.create: continue
		plan.resource = store.ensure_resource(plan.uri)
		if not plan.resource: return host.fail("SOURCE_UNAVAILABLE", "Cannot obtain the live source resource.", {"uri": plan.uri})
	for plan: Dictionary in plans:
		if plan.create:
			plan.resource = GDScript.new() if plan.uri.ends_with(".gd") else Shader.new()
			plan.resource.resource_path = plan.uri
			host.register_resource(plan.resource)
	var context: Resource = plans[0].resource
	host.begin_edit("Edit source documents", context)
	var undo: EditorUndoRedoManager = host.get_undo_redo()
	var guards: Array = []
	for plan: Dictionary in plans:
		undo.add_do_method(store, "set_source", plan.uri, plan.source, plan.resource)
		undo.add_undo_method(store, "restore_source", plan.uri, plan.before)
		guards.append({"check": store.source_matches.bind(plan.uri, str(plan.source).sha256_text())})
	var result: Dictionary = host.finish_edit(context, "Edit source documents", guards)
	await host.get_tree().process_frame
	# Validation receives the final sources of every file, including unsaved dependencies.
	result.validation = await validate_sources(uris)
	if result.validation.has("error"):
		result.validation = validator.unavailable(uris, {}, result.validation.error.message)
	var source_changed: bool = false
	for guard: Dictionary in guards:
		if not guard.check.call(): source_changed = true
	result.persistence = {"saved": [], "failed": [], "complete": true}
	if p.get("save", false) and not source_changed:
		result.persistence = await save_documents({"uris": uris})
	elif p.get("save", false):
		result.persistence = {"saved": [], "failed": [{"error": "Source changed during validation; nothing was saved."}], "complete": false}
	result.documents = []
	result.pending_save = []
	var retained: Array = []
	var valid: bool = result.persistence.complete and not source_changed
	var has_drafts: bool = false
	for overlay_uri: String in store.overlays():
		if not FileAccess.file_exists(overlay_uri): has_drafts = true
	for diagnostic: Dictionary in result.validation.sources:
		if diagnostic.get("valid") != true: valid = false
	for plan: Dictionary in plans:
		var document: Dictionary = document_state(plan.uri)
		result.documents.append(document)
		if not document.get("saved", false): result.pending_save.append(plan.uri)
		if plan.create and FileAccess.file_exists(plan.uri): retained.append(plan.uri)
		# Update the same live resource only after the coherent validation result exists.
		if plan.resource is Script and has_drafts:
			# A preload cannot resolve a never-saved file in the live editor.
			# Keep the valid draft without triggering misleading compiler errors.
			document.live_reload = "deferred"
		elif plan.resource is Script and not source_changed:
			var reloaded: Error = plan.resource.reload(true)
			document.live_reload = "succeeded" if reloaded == OK else "failed"
			if reloaded != OK: valid = false
		elif plan.resource is Shader: plan.resource.get_rid()
	result.status = "completed" if valid else "partial"
	result.summary = "Source changes applied and validated." if valid else "Source changes remain applied; inspect document, validation, and persistence results before continuing."
	result.undo = {"edit_id": result.edit_id, "scope": ["live_sources"], "retained_files": retained, "note": "Undo restores live source edits and removes never-saved drafts; already-saved files remain on disk."}
	result.saved = result.pending_save.is_empty()
	return result

func save_documents(p: Dictionary) -> Dictionary:
	var saved: Array = []
	var failed: Array = []
	var before_sources: Dictionary = {}
	for uri: String in store.overlays():
		var info: Dictionary = source_info(uri)
		if not info.has("error"): before_sources[uri] = info.disk_revision
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
			var conflicts: Array = store.conflicts()
			if not conflicts.is_empty():
				failed.append({"uri": uri, "code": "EXTERNAL_CHANGE", "error": "Scene saving may also save conflicting source buffers.", "conflicts": conflicts})
				continue
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
					if target != uri:
						resource.take_over_path(target)
						host.resources.erase(uri)
						host.register_resource(resource)
						store.move_state(uri, target)
					store.mark_saved(target)
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
	var also_saved: Array = []
	for uri: String in before_sources:
		var info: Dictionary = source_info(uri)
		if not info.has("error") and not info.unsaved and info.disk_revision != before_sources[uri] and uri not in p.get("uris", []):
			also_saved.append(uri)
	return {"saved": saved, "failed": failed, "also_saved": also_saved, "also_saved_scope": "observed source buffers; Godot scene saves may persist other linked resources", "complete": failed.is_empty(), "status": "completed" if failed.is_empty() else ("partial" if not saved.is_empty() else "failed"), "summary": "Requested documents saved." if failed.is_empty() else "Some documents were not saved; successful saves remain on disk.", "undo": {"scope": [], "note": "Saving is not an editor undo operation. Undoing an edit does not restore disk files."}}

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
	var uris: Array = p.get("uris", [])
	for uri: String in uris:
		var info: Dictionary = source_info(uri)
		if info.has("error"): return info
		if p.has("revision") and p.revision != info.revision: return host.fail("STALE_REVISION", "Diagnostics requested for an old source revision.", {"current_revision": info.revision})
	var checked: Dictionary = {"sources": []} if uris.is_empty() else await validate_sources(uris)
	if checked.has("error"): return checked
	var kinds: Array = p.get("kinds", [])
	var result: Dictionary = host.logs.read(int(p.get("since", 0)), int(p.get("limit", 200)), kinds)
	for source: Dictionary in checked.sources:
		source.entries = LogBuffer.filter_entries(source.entries, kinds)
	result.sources = checked.sources
	result.entries_are_history = true
	result.origin = "editor"
	if checked.has("snapshot_id"): result.snapshot_id = checked.snapshot_id
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
