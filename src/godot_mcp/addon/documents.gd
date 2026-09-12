@tool
extends RefCounted
## Source editing and explicit persistence, including Godot's linked-resource saves.
var host: EditorPlugin
const DocumentResult = preload("res://addons/godot_mcp/document_result.gd")
const SourceStore = preload("res://addons/godot_mcp/source_store.gd")
const SourceValidation = preload("res://addons/godot_mcp/source_validation.gd")
const SourceSearch = preload("res://addons/godot_mcp/source_search.gd")
const SourceOperations = preload("res://addons/godot_mcp/source_operations.gd")
const SourceDiagnostics = preload("res://addons/godot_mcp/source_diagnostics.gd")
var store: RefCounted
var validator: RefCounted
var search: RefCounted
var operations: RefCounted
var diagnostics: RefCounted
var owned_breakpoints: Dictionary = {}

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host
	store = SourceStore.new(host)
	validator = SourceValidation.new(host)
	search = SourceSearch.new(host, store)
	operations = SourceOperations.new(host)
	diagnostics = SourceDiagnostics.new(host)

func handles(method: String) -> bool:
	return method in ["find_assets", "read_scripts", "_source_snapshot", "_apply_source_plan", "resume_script_changes", "save_documents", "update_signals", "get_diagnostics", "get_logs"]

func dispatch(method: String, p: Dictionary) -> Dictionary:
	match method:
		"find_assets": return find_assets(p)
		"read_scripts": return read_scripts(p)
		"_source_snapshot": return source_snapshot(p)
		"_apply_source_plan": return await operations.start(p)
		"resume_script_changes": return operations.resume(p)
		"save_documents": return await save_documents(p)
		"update_signals": return update_signals(p)
		"get_diagnostics": return diagnostics.start(p)
		"get_logs": return await get_logs(p)
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
	return search.symbols(source)

func offset(source: String, position: Dictionary) -> int:
	var lines: PackedStringArray = source.split("\n")
	var line: int = int(position.get("line", 0)) - 1
	var column: int = int(position.get("column", 0)) - 1
	if line < 0 or line >= lines.size() or column < 0 or column > lines[line].length(): return -1
	var index: int = column
	for i: int in line: index += lines[i].length() + 1
	return index

func read_source(p: Dictionary) -> Dictionary:
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
	result.symbols_truncated = result.symbols.size() > 10000
	result.symbols = result.symbols.slice(0, 10000)
	return result

func read_scripts(p: Dictionary) -> Dictionary:
	var records: Array = []
	var revisions: Dictionary = {}
	var bytes: int = 0
	for request: Dictionary in p.get("documents", []):
		if revisions.has(request.get("uri", "")): return host.fail("DUPLICATE_DOCUMENT", "Read each URI once per request.")
		var result: Dictionary = read_source(request)
		if result.has("error"): return result
		bytes += JSON.stringify(result).to_utf8_buffer().size()
		if bytes > 8 * 1024 * 1024: return host.fail("SOURCE_LIMIT", "Read responses are limited to 8 MiB; request fewer sources or source ranges.")
		records.append(result)
		revisions[result.uri] = result.revision
	return {"documents": records, "base_revisions": revisions, "editor_epoch": host.epoch}

func source_snapshot(p: Dictionary) -> Dictionary:
	var records: Array = []
	var seen: Dictionary = {}
	var bytes: int = 0
	for request: Dictionary in p.get("documents", []):
		var uri: String = str(request.get("uri", ""))
		if seen.has(uri): return host.fail("DUPLICATE_DOCUMENT", "Prepare each URI once per patch.")
		seen[uri] = true
		var info: Dictionary = source_info(uri)
		if request.get("create", false):
			if not info.has("error"): return host.fail("ALREADY_EXISTS", "The source or draft already exists.", {"uri": uri})
			if info.error.code != "FILE_NOT_FOUND": return info
			records.append({"uri": uri, "revision": null, "disk_revision": null})
			continue
		if info.has("error"): return info
		if info.external_change: return host.fail("EXTERNAL_CHANGE", "Resolve conflicting editor and disk changes before preparing a patch.", {"uri": uri, "revision": info.revision, "disk_revision": info.disk_revision, "conflict": info.conflict})
		var base: Dictionary = store.base_source(uri, str(request.get("base_revision", "")))
		if base.has("error"): return base
		bytes += str(info.source).to_utf8_buffer().size() + str(base.source).to_utf8_buffer().size()
		if bytes > 16 * 1024 * 1024: return host.fail("SOURCE_LIMIT", "Patch preparation is limited to 16 MiB of base and current text.")
		records.append({"uri": uri, "source": info.source, "revision": info.revision, "disk_revision": info.disk_revision, "base_source": base.source, "base_revision": base.revision})
	return {"documents": records, "editor_epoch": host.epoch}

func validate_sources(uris: Array) -> Dictionary:
	var overlays: Dictionary = store.overlays()
	var conflicts: Array = store.conflicts()
	if not conflicts.is_empty(): return host.fail("EXTERNAL_CHANGE", "Resolve source buffer and disk conflicts before validation.", {"conflicts": conflicts})
	var settings: Dictionary = host.assets.settings_snapshot()
	if settings.has("error"): return settings
	overlays["res://project.godot"] = settings.source
	var revisions: Dictionary = {}
	for uri: String in uris:
		var info: Dictionary = source_info(uri)
		if info.has("error"): return info
		if info.external_change: return host.fail("EXTERNAL_CHANGE", "Resolve conflicting disk and unsaved source changes before validation.", {"uri": uri})
		overlays[uri] = info.source
		revisions[uri] = info.revision
	var result: Dictionary = await validator.check(uris, overlays, revisions)
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

func resource_storage(resource: Resource) -> String:
	var uri: String = resource.resource_path
	var source: String = uri.get_slice("::", 0)
	if source.contains("/.godot/imported/") or (not source.is_empty() and FileAccess.file_exists(source + ".import")): return "imported"
	if uri.contains("::"): return "embedded"
	if not uri.begins_with("res://"): return "memory"
	return "document" if uri.get_extension() in ResourceSaver.get_recognized_extensions(resource) else "external"

func save_plan(uris: Array) -> Dictionary:
	var scene_save: bool = false
	for uri: String in uris:
		if uri.ends_with(".tscn"): scene_save = true
	var additional: Array = []
	if scene_save:
		# Godot scene persistence also saves edited external resources. Surface
		# their scope before calling the native save entry point.
		for uri: String in store.overlays():
			if uri not in uris and uri not in additional: additional.append(uri)
		for uri: String in host.dirty_resources():
			if resource_storage(host.resources[uri]) == "document" and uri not in uris and uri not in additional: additional.append(uri)
	additional.sort()
	return {"uris": uris.duplicate(), "additional_uris": additional, "scope": "requested documents and observed edited external resources persisted by Godot scene saves"}

func _write_source(target: String, source: String) -> Error:
	# GDScript and shader format savers write plain text. Doing that here avoids
	# ResourceSaver's editor callback until every source in the bundle exists.
	var error: Error = DirAccess.make_dir_recursive_absolute(target.get_base_dir())
	if error != OK: return error
	var temporary: String = target.get_base_dir().path_join("." + target.get_file() + ".mcp-" + host.epoch + "-" + str(Time.get_ticks_usec()))
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if not file: return FileAccess.get_open_error()
	file.store_string(source)
	file.flush()
	error = file.get_error()
	file.close()
	if error == OK and FileAccess.file_exists(target):
		var permissions: int = FileAccess.get_unix_permissions(target)
		if permissions >= 0: FileAccess.set_unix_permissions(temporary, permissions)
	if error == OK: error = DirAccess.rename_absolute(temporary, target)
	if error != OK: DirAccess.remove_absolute(temporary)
	return error

func _publish_saved_sources(uris: Array, saved: Array) -> void:
	var current: Array = uris.duplicate()
	for item: Dictionary in saved:
		if item.uri not in uris or item.uri == item.saved_as: continue
		var resource: Resource = host.resource_uri(item.uri)
		if resource:
			resource.take_over_path(item.saved_as)
			host.resources.erase(item.uri)
			host.register_resource(resource)
		store.move_state(item.uri, item.saved_as)
		current[current.find(item.uri)] = item.saved_as
	# Failed saves still leave the requested edits available as unsaved sources.
	# They are published only after the complete write attempt, never between files.
	store.publish_sources(current)
	for item: Dictionary in saved:
		if item.uri not in uris: continue
		store.mark_saved(item.saved_as)
	# The native filesystem owner retains/creates UID sidecars and updates its
	# class registry. All source bytes and live scripts are now available to it.
	for item: Dictionary in saved:
		if item.uri in uris: EditorInterface.get_resource_filesystem().update_file(item.saved_as)

func save_documents(p: Dictionary) -> Dictionary:
	var plan: Dictionary = save_plan(p.get("uris", []))
	if not plan.additional_uris.is_empty():
		return host.fail("SAVE_SCOPE_REQUIRED", "Saving these scenes may persist other edited documents. Include their paths explicitly, or reconcile them first.", {"save_plan": plan, "recovery": {"tool": "save_documents", "arguments": {"uris": plan.uris + plan.additional_uris}}})
	var saved: Array = []
	var failed: Array = []
	var before_sources: Dictionary = {}
	for uri: String in store.overlays():
		var info: Dictionary = source_info(uri)
		if not info.has("error"): before_sources[uri] = info.disk_revision
	var view: Dictionary = {"scene": host.scene_access.active_path(), "selection": host.scene_access.selection(), "target": ""}
	var receipt: Dictionary = {"editor_epoch": host.epoch, "request_id": host.active_request.get("request_id"), "operation_id": host.active_request.get("operation_id"), "state": "pending", "phase": "preparing", "documents": [], "recorded_at": Time.get_datetime_string_from_system(true)}
	for uri: String in p.get("uris", []): receipt.documents.append({"uri": uri, "target": p.get("save_as", {}).get(uri, uri), "state": "not_attempted"})
	_write_save_receipt(receipt)
	var source_uris: Array = []
	var source_indices: Array = []
	var other_indices: Array = []
	for index: int in p.get("uris", []).size():
		if str(p.uris[index]).get_extension() in ["gd", "gdshader"]:
			source_uris.append(p.uris[index])
			source_indices.append(index)
		else: other_indices.append(index)
	var sources_published: bool = false
	var source_failed: bool = false
	for request_index: int in source_indices + other_indices:
		var uri: String = p.uris[request_index]
		if request_index in other_indices and not sources_published:
			source_failed = not failed.is_empty()
			_publish_saved_sources(source_uris, saved)
			sources_published = true
		if source_failed:
			failed.append({"uri": uri, "index": request_index, "code": "SOURCE_SAVE_FAILED", "error": "A source in this save bundle failed; dependent document saves were not attempted."})
			continue
		receipt.phase = "saving"
		receipt.documents[request_index].state = "outcome_unknown"
		_write_save_receipt(receipt)
		var target: String = str(p.get("save_as", {}).get(uri, uri))
		if not target.begins_with("res://") or not host.paths_safe(target):
			failed.append({"uri": uri, "index": request_index, "code": "INVALID_PATH", "error": "A res:// save_as path is required for an in-memory resource."})
			continue
		if target != uri and FileAccess.file_exists(target):
			failed.append({"uri": uri, "index": request_index, "code": "ALREADY_EXISTS", "error": "save_as destination already exists."})
			continue
		var error: Error = OK
		if uri == "res://project.godot":
			if target != uri: error = ERR_INVALID_PARAMETER
			else: error = ProjectSettings.save()
		elif uri.ends_with(".tscn"):
			var conflicts: Array = store.conflicts()
			if not conflicts.is_empty():
				failed.append({"uri": uri, "index": request_index, "code": "EXTERNAL_CHANGE", "error": "Scene saving may also save conflicting source buffers.", "conflicts": conflicts})
				continue
			var activated: Dictionary = await host.scene_access.activate(uri)
			if activated.has("error"):
				error = ERR_FILE_NOT_FOUND
			else:
				view.target = uri
				view.expected_selection = host.scene_access.selection()
				receipt.phase = "native_scene_save"
				_write_save_receipt(receipt)
				if target == uri:
					error = EditorInterface.save_scene()
				else:
					DirAccess.make_dir_recursive_absolute(target.get_base_dir())
					EditorInterface.save_scene_as(target, false)
					error = OK if host.scene_access.active_path() == target and FileAccess.file_exists(target) else ERR_FILE_CANT_WRITE
					view.target = target
		elif uri.get_extension() in ["gd", "gdshader"]:
			var info: Dictionary = source_info(uri)
			if info.has("error") or info.get("external_change", false):
				failed.append({"uri": uri, "index": request_index, "code": str(info.error.get("code", "FILE_NOT_FOUND")) if info.has("error") else "EXTERNAL_CHANGE", "error": "Source is missing or disk changes conflict with unsaved edits.", "conflicts": store.conflicts([uri])})
				continue
			error = _write_source(target, info.source) if target.get_extension() == uri.get_extension() else ERR_INVALID_PARAMETER
		else:
			var resource: Resource = host.resource_uri(uri)
			if not resource: error = ERR_FILE_NOT_FOUND
			elif target == uri and resource_storage(resource) != "document":
				failed.append({"uri": uri, "index": request_index, "code": "IMPORTED_RESOURCE" if resource_storage(resource) == "imported" else "SAVE_AS_REQUIRED", "error": "This resource is not a directly saved document. Save an authored copy to a new .tres or .res path; its source remains unchanged."})
				continue
			elif target.get_extension() not in ResourceSaver.get_recognized_extensions(resource): error = ERR_INVALID_PARAMETER
			else:
				DirAccess.make_dir_recursive_absolute(target.get_base_dir())
				# Keep imported identity and its users intact when exporting a copy.
				var imported_copy: bool = resource_storage(resource) == "imported"
				if imported_copy: resource = resource.duplicate(true)
				error = ResourceSaver.save(resource, target, ResourceSaver.FLAG_CHANGE_PATH)
				if error == OK:
					host.register_resource(resource)
					EditorInterface.set_object_edited(resource, false)
		if error == OK:
			saved.append({"uri": uri, "saved_as": target, "index": request_index})
			receipt.documents[request_index].state = "saved"
			receipt.documents[request_index].disk_revision = FileAccess.get_sha256(target)
			_write_save_receipt(receipt)
			if uri not in source_uris: EditorInterface.get_resource_filesystem().update_file(target)
		else:
			failed.append({"uri": uri, "index": request_index, "code": "SAVE_FAILED", "error": error_string(error)})
	if not sources_published: _publish_saved_sources(source_uris, saved)
	for failure: Dictionary in failed:
		receipt.documents[int(failure.index)].state = "not_attempted" if failure.code == "SOURCE_SAVE_FAILED" else "failed"
		receipt.documents[int(failure.index)].error = failure
	receipt.state = "completed" if failed.is_empty() else "partial" if not saved.is_empty() else "failed"
	receipt.phase = "finished"
	_write_save_receipt(receipt)
	await host.scene_access.leave(view)
	await host.get_tree().process_frame
	var also_saved: Array = []
	for uri: String in before_sources:
		var info: Dictionary = source_info(uri)
		if not info.has("error") and not info.unsaved and info.disk_revision != before_sources[uri] and uri not in p.get("uris", []):
			also_saved.append(uri)
	var result: Dictionary = DocumentResult.begin({"edit_id": null, "scope": [], "note": "Saving is not an editor undo operation. Undoing an edit does not restore disk files."})
	result.save_receipt = {"uri": "res://.godot-mcp/last-save.json", "retained": receipt.get("retained", false)}
	result.save_observation = "observed source buffers; Godot scene saves may persist other linked resources"
	for item: Dictionary in saved:
		var record: Dictionary = persistence_document(item.saved_as, "saved")
		record.save = {"state": "saved", "index": item.index}
		if item.uri != item.saved_as: record.save.previous_uri = item.uri
		DocumentResult.put(result, record)
	for item: Dictionary in failed:
		var record: Dictionary = persistence_document(item.uri)
		var target: String = str(p.get("save_as", {}).get(item.uri, item.uri))
		record.save = {"state": "skipped" if item.code == "SOURCE_SAVE_FAILED" else "failed", "index": item.index}
		if target != item.uri: record.save.target = target
		DocumentResult.put(result, record)
		var retry_args: Dictionary = {"uris": [item.uri]}
		if target != item.uri: retry_args.save_as = {item.uri: target}
		var recovery: Dictionary = {"tool": "save_documents", "arguments": retry_args, "prerequisite": "Resolve the reported conflict or destination problem before retrying this save."}
		if item.get("code") == "EXTERNAL_CHANGE":
			recovery = {"tool": "get_context", "arguments": {"scope": "editor"}, "prerequisite": "Resolve source/disk conflicts before saving; preserve the applied source edits."}
		var details: Dictionary = {"index": item.index}
		if item.has("conflicts") and not item.conflicts.is_empty(): details.conflicts = item.conflicts
		DocumentResult.failure(result, "save", item.get("code", "SAVE_FAILED"), item.error, {"uri": item.uri}, recovery, details)
	for uri: String in also_saved:
		var record: Dictionary = persistence_document(uri, "saved")
		record.save = {"state": "saved", "requested": false}
		DocumentResult.put(result, record)
	return DocumentResult.finish(result, not saved.is_empty() or not also_saved.is_empty())

func persistence_document(uri: String, effect: String = "") -> Dictionary:
	# Non-source saves report their persistence outcome without claiming a source
	# revision or a live-buffer state that the source store does not observe.
	var state: Dictionary = document_state(uri) if uri.get_extension() in ["gd", "gdshader"] else {"uri": uri}
	return DocumentResult.document(state, effect)

func find_assets(p: Dictionary) -> Dictionary:
	return search.search(p)

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

func _write_save_receipt(receipt: Dictionary) -> void:
	const PATH := "res://.godot-mcp/last-save.json"
	var file := FileAccess.open(PATH + ".tmp", FileAccess.WRITE)
	if not file:
		receipt.retained = false
		return
	file.store_string(JSON.stringify(receipt))
	file.flush()
	file.close()
	receipt.retained = DirAccess.rename_absolute(PATH + ".tmp", PATH) == OK

func last_save() -> Dictionary:
	const PATH := "res://.godot-mcp/last-save.json"
	if not FileAccess.file_exists(PATH): return {}
	var value: Variant = JSON.parse_string(FileAccess.get_file_as_string(PATH))
	if not value is Dictionary: return {"state": "unavailable"}
	value.interrupted = value.get("state") == "pending" and value.get("editor_epoch") != host.epoch
	value.note = "Last save receipt only; outcome_unknown entries require inspecting current disk files. No automatic replay."
	return value

func get_logs(p: Dictionary) -> Dictionary:
	var result: Dictionary
	if p.has("run_id"):
		if p.run_id != host.runtime.run_id or not host.runtime.ready: return host.fail("STALE_RUN", "No matching runtime.")
		result = await host.debugger.request("get_diagnostics", p)
		result.run_id = p.run_id
		result.origin = "runtime"
	else:
		result = host.logs.read(int(p.get("since", 0)), int(p.get("limit", 200)), p.get("kinds", []))
		result.origin = "editor"
	result.history = true
	result.current_verdict = false
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
