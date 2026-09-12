@tool
extends EditorPlugin
## All editor mutations are serialized here, on Godot's main thread.
const Version = preload("res://addons/godot_mcp/version.gd")
const Codec = preload("res://addons/godot_mcp/codec.gd")
const ResourceTarget = preload("res://addons/godot_mcp/resource_target.gd")
const PropertyEdits = preload("res://addons/godot_mcp/property_edits.gd")
const OperationRecords = preload("res://addons/godot_mcp/operation_records.gd")
const LogBuffer = preload("res://addons/godot_mcp/log_buffer.gd")
const SceneAccess = preload("res://addons/godot_mcp/scene_access.gd")
const EditorUndo = preload("res://addons/godot_mcp/editor_undo.gd")
const Scenes = preload("res://addons/godot_mcp/scenes.gd")
const Documents = preload("res://addons/godot_mcp/documents.gd")
const Resources = preload("res://addons/godot_mcp/resources.gd")
const Animations = preload("res://addons/godot_mcp/animations.gd")
const Tiles = preload("res://addons/godot_mcp/tiles.gd")
const Assets = preload("res://addons/godot_mcp/assets.gd")
const Runtime = preload("res://addons/godot_mcp/runtime_tools.gd")
const Debugger = preload("res://addons/godot_mcp/debugger.gd")
var listener := TCPServer.new()
var peers: Array[Dictionary] = []
var token: String = ""
var epoch: String = ""
var busy: bool = false:
	set(value):
		busy = value
		if not value: active_request.clear()
var active_request: Dictionary = {}
var scene_access: RefCounted
var editor_undo: RefCounted
var main_screen: String = ""
var enabled: bool = false
var added_autoload: bool = false
var resources: Dictionary = {}
var edits: Array[Dictionary] = []
var modules: Array[RefCounted] = []
var documents: RefCounted
var resource_targets: RefCounted
var property_edits: RefCounted
var operation_records: RefCounted
var assets: RefCounted
var runtime: RefCounted
var debugger: EditorDebuggerPlugin
var logs: Logger
var status_label: Label
var registry_path: String = ""
var edit_parent: Dictionary = {}

func _enter_tree() -> void:
	var engine: Dictionary = Engine.get_version_info()
	var actual := "%s.%s.%s" % [engine.major, engine.minor, engine.patch]
	status_label = Label.new()
	add_control_to_container(CONTAINER_TOOLBAR, status_label)
	if actual != Version.ENGINE:
		status_label.text = "Godot MCP · Unsupported Godot " + actual
		return
	epoch = Crypto.new().generate_random_bytes(8).hex_encode()
	token = Crypto.new().generate_random_bytes(32).hex_encode()
	logs = LogBuffer.new()
	OS.add_logger(logs)
	scene_access = SceneAccess.new(self)
	editor_undo = EditorUndo.new(self)
	main_screen_changed.connect(func(screen: String) -> void: main_screen = screen)
	documents = Documents.new(self)
	resource_targets = ResourceTarget.new(self)
	property_edits = PropertyEdits.new(self)
	operation_records = OperationRecords.new(self)
	runtime = Runtime.new(self)
	assets = Assets.new(self)
	modules = [Scenes.new(self), documents, Resources.new(self), Animations.new(self), Tiles.new(self), assets, runtime]
	debugger = Debugger.new()
	debugger.host = self
	add_debugger_plugin(debugger)
	var autoload: String = ProjectSettings.get_setting("autoload/GodotMCPRuntime", "")
	var autoload_path: String = autoload.trim_prefix("*")
	if autoload_path.begins_with("uid://"):
		autoload_path = ResourceUID.get_id_path(ResourceUID.text_to_id(autoload_path))
	if not autoload.is_empty() and autoload_path != "res://addons/godot_mcp/runtime.gd":
		status_label.text = "Godot MCP · Autoload name conflict"
		return
	if autoload.is_empty():
		add_autoload_singleton("GodotMCPRuntime", "res://addons/godot_mcp/runtime.gd")
		added_autoload = true
		# Persist the new helper before the first child process loads project.godot.
		var saved: Error = ProjectSettings.save()
		if saved != OK:
			status_label.text = "Godot MCP · Cannot save runtime autoload"
			return
	var error: Error = listener.listen(0, "127.0.0.1")
	if error != OK:
		status_label.text = "Godot MCP · " + error_string(error)
		return
	DirAccess.make_dir_recursive_absolute("res://.godot-mcp")
	FileAccess.set_unix_permissions("res://.godot-mcp", 448)
	var file := FileAccess.open("res://.godot-mcp/endpoint.json", FileAccess.WRITE)
	if not file:
		listener.stop()
		status_label.text = "Godot MCP · Cannot write endpoint"
		return
	var settings := EditorInterface.get_editor_settings()
	var dap_port: int = int(settings.get_setting("network/debug_adapter/remote_port"))
	file.store_string(JSON.stringify({"project": ProjectSettings.globalize_path("res://").trim_suffix("/"), "port": listener.get_local_port(), "token": token, "epoch": epoch, "version": Version.PRODUCT, "protocol": Version.PROTOCOL, "pid": OS.get_process_id(), "dap_port": dap_port}))
	file.close()
	FileAccess.set_unix_permissions("res://.godot-mcp/endpoint.json", 384)
	_register_editor()
	status_label.text = "Godot MCP · Ready"
	status_label.tooltip_text = Version.PRODUCT + " · Local connections only"
	enabled = true
	set_process(true)

func _exit_tree() -> void:
	set_process(false)
	if editor_undo: editor_undo.shutdown()
	if documents:
		documents.operations.shutdown()
		documents.diagnostics.shutdown()
		documents.validator.shutdown()
		documents.store.shutdown()
	if assets:
		assets.imports.shutdown()
		assets.deletions.shutdown()
	for item: Dictionary in peers:
		item.peer.close()
	peers.clear()
	listener.stop()
	if enabled and FileAccess.file_exists("res://.godot-mcp/endpoint.json"):
		var saved: Variant = JSON.parse_string(FileAccess.get_file_as_string("res://.godot-mcp/endpoint.json"))
		if saved is Dictionary and saved.get("epoch") == epoch:
			DirAccess.remove_absolute("res://.godot-mcp/endpoint.json")
	if not registry_path.is_empty() and FileAccess.file_exists(registry_path):
		var registered: Variant = JSON.parse_string(FileAccess.get_file_as_string(registry_path))
		if registered is Dictionary and registered.get("epoch") == epoch:
			DirAccess.remove_absolute(registry_path)
	if debugger:
		remove_debugger_plugin(debugger)
	if added_autoload and ProjectSettings.get_setting("autoload/GodotMCPRuntime", "") == "*res://addons/godot_mcp/runtime.gd":
		remove_autoload_singleton("GodotMCPRuntime")
	if logs:
		OS.remove_logger(logs)
	if is_instance_valid(status_label):
		remove_control_from_container(CONTAINER_TOOLBAR, status_label)
		status_label.queue_free()
	resources.clear()

func _register_editor() -> void:
	var install_file := "res://.godot-mcp/install.json"
	if not FileAccess.file_exists(install_file):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(install_file))
	if not parsed is Dictionary or not parsed.get("home", "") is String or str(parsed.home).is_empty():
		status_label.text = "Godot MCP · Invalid install configuration"
		return
	var home: String = str(parsed.home)
	if not home.is_absolute_path():
		status_label.text = "Godot MCP · Install home must be absolute"
		return
	var project: String = ProjectSettings.globalize_path("res://").trim_suffix("/")
	var key: String = project.sha256_text()
	var editors := home.path_join("editors")
	if DirAccess.make_dir_recursive_absolute(editors) != OK:
		status_label.text = "Godot MCP · Cannot create editor registry"
		return
	FileAccess.set_unix_permissions(editors, 448)
	registry_path = editors.path_join(key + ".json")
	var file := FileAccess.open(registry_path, FileAccess.WRITE)
	if not file:
		registry_path = ""
		status_label.text = "Godot MCP · Cannot write editor registry"
		return
	file.store_string(JSON.stringify({"project": project, "epoch": epoch}))
	file.close()
	FileAccess.set_unix_permissions(registry_path, 384)

func _process(_delta: float) -> void:
	while listener.is_connection_available():
		var stream := listener.take_connection()
		if peers.size() >= 32:
			stream.disconnect_from_host()
			continue
		var peer := WebSocketPeer.new()
		peer.inbound_buffer_size = 32 * 1024 * 1024
		peer.outbound_buffer_size = 32 * 1024 * 1024
		peer.accept_stream(stream)
		peers.append({"peer": peer, "time": Time.get_ticks_msec(), "authenticated": false})
	for item: Dictionary in peers.duplicate():
		var peer: WebSocketPeer = item.peer
		peer.poll()
		if peer.get_ready_state() == WebSocketPeer.STATE_CLOSED:
			peers.erase(item)
			continue
		if not item.authenticated and Time.get_ticks_msec() - item.time > 5000:
			peer.close(1008, "Authentication required")
		while peer.get_available_packet_count() > 0:
			var request: Variant = JSON.parse_string(peer.get_packet().get_string_from_utf8())
			if not request is Dictionary:
				peer.close(1002, "Expected JSON object")
				break
			if request.get("token", "") != token:
				_respond(peer, request.get("id"), fail("UNAUTHORIZED", "Invalid project token."))
				peer.close(1008, "Unauthorized")
				break
			item.authenticated = true
			if not request.get("params", {}) is Dictionary:
				_respond(peer, request.get("id"), fail("INVALID_ARGUMENT", "params must be an object."))
			elif not paths_safe(request.get("params", {})):
				_respond(peer, request.get("id"), fail("INVALID_PATH", "Project path contains traversal or a symlink."))
			elif busy and request.get("method", "") == "get_operation_result":
				_respond(peer, request.get("id"), operation_result(str(request.get("params", {}).get("operation_id", ""))))
			elif busy and request.get("method", "") == "get_context":
				_respond(peer, request.get("id"), progress())
			elif busy and request.get("method", "") == "get_logs" and not request.get("params", {}).has("run_id"):
				_respond(peer, request.get("id"), await documents.get_logs(request.get("params", {})))
			elif busy:
				if not documents.operations.script_operations(request.get("params", {})).is_empty(): _execute(peer, request)
				else: _respond(peer, request.get("id"), fail("EDITOR_BUSY", "Wait for the reported editor operation before retrying this request.", progress()))
			else:
				_execute(peer, request)

func _respond(peer: WebSocketPeer, id: Variant, result: Dictionary) -> void:
	if peer.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	var response: Dictionary = {"id": id}
	if result.has("error"):
		response.error = result.error
	else:
		response.result = result
	var payload: String = JSON.stringify(response)
	# Godot leaves some control bytes (notably ANSI ESC from logs) literal.
	# String.chr(0) is invalid in Godot.
	for code: int in range(1, 32):
		payload = payload.replace(String.chr(code), "\\u%04x" % code)
	peer.send_text(payload)

func _execute(peer: WebSocketPeer, request: Dictionary) -> void:
	var prepared: Dictionary = await documents.operations.wait_for_scripts(request.get("params", {}))
	if prepared.has("error"):
		_respond(peer, request.get("id"), prepared)
		return
	enter_busy(str(request.get("method", "request")))
	active_request.request_id = request.get("id")
	var since: int = logs.mark()
	status_label.text = "Godot MCP · " + str(request.get("method", "request"))
	var result: Dictionary = await dispatch(str(request.get("method", "")), request.get("params", {}))
	if result.is_empty(): result = fail("INTEGRATION_ERROR", "The handler did not complete. Read get_logs and inspect the reported state before retrying; a change may already have applied.", {"outcome": "unknown", "active_scene": scene_access.active_path(), "last_edit_id": edits.back().edit_id if not edits.is_empty() else null, "recovery": {"tool": "get_logs", "arguments": {"since": since, "kinds": ["error", "warning"]}}})
	annotate_editor_logs(result, since)
	_respond(peer, request.get("id"), result)
	busy = false
	if is_instance_valid(status_label):
		status_label.text = "Godot MCP · Ready"

func enter_busy(tool: String, operation_id: String = "", phase: String = "executing") -> void:
	busy = true
	active_request = {"tool": tool, "phase": phase, "started_at_msec": Time.get_ticks_msec()}
	if not operation_id.is_empty(): active_request.operation_id = operation_id

func progress() -> Dictionary:
	var active: Dictionary = active_request.duplicate(true)
	if not active.is_empty(): active.elapsed_ms = Time.get_ticks_msec() - int(active.started_at_msec)
	var fs := EditorInterface.get_resource_filesystem()
	var result: Dictionary = {"editor_epoch": epoch, "busy": busy, "active_operation": active, "filesystem": {"scanning": fs.is_scanning(), "importing": fs.is_importing()}, "pending_operations": assets.imports.pending() + documents.operations.pending() + documents.diagnostics.pending() + assets.deletions.pending()}
	result.recovery = {"tool": "get_operation_result", "arguments": {"operation_id": active.operation_id, "wait_ms": 1500}} if active.has("operation_id") else {"tool": "get_context", "arguments": {"scope": "progress"}}
	return result

func annotate_editor_logs(result: Dictionary, since: int) -> void:
	var observed: Dictionary = logs.read(since, 3, ["error", "warning"])
	if observed.entries.is_empty(): return
	for entry: Dictionary in observed.entries:
		entry.erase("backtraces")
		entry.erase("code")
		entry.message = str(entry.message).left(500)
	var events: Dictionary = {"since": since, "through": logs.mark(), "entries": observed.entries, "has_more": observed.has_more, "association": "observed during this operation; background errors may be unrelated", "recovery": {"tool": "get_logs", "arguments": {"since": since, "kinds": ["error", "warning"]}}}
	if result.has("error"): result.error.get_or_add("details", {})["editor_events"] = events
	else: result.editor_events = events

func dispatch(method: String, p: Dictionary) -> Dictionary:
	if method in ["get_scene", "create_nodes", "update_nodes", "delete_nodes", "update_signals", "get_resource", "create_resource", "update_resource", "get_animation", "edit_animation", "edit_animation_graph", "preview_animation", "get_tilemap", "edit_tileset", "paint_tiles", "_apply_source_plan"]:
		var previous: Dictionary = await scene_access.enter(p)
		if previous.has("error"): return previous
		var result: Dictionary = await _dispatch(method, p)
		await scene_access.leave(previous)
		return result
	return await _dispatch(method, p)

func _dispatch(method: String, p: Dictionary) -> Dictionary:
	match method:
		"get_context":
			var result: Dictionary = context(p)
			if p.get("runtime_details", false): result.source_provenance = await runtime.details()
			return result
		"undo_edit": return await undo_edit(p)
		"get_operation_result": return operation_result(str(p.get("operation_id", "")))
		"_debug_state": return debugger.state()
		"_breakpoints": return documents.breakpoints(p)
	for module: RefCounted in modules:
		if module.handles(method):
			if method == "save_documents":
				var reservation: Dictionary = operation_records.begin(method)
				if reservation.has("error"): return reservation
				var result: Dictionary = await module.dispatch(method, p)
				if result.has("error") or result.is_empty():
					operation_records.discard(reservation.operation_id)
					return result
				result.operation_id = reservation.operation_id
				result.details_retained = operation_records.publish(reservation.operation_id, result)
				return result
			return await module.dispatch(method, p)
	return fail("UNKNOWN_TOOL", "Unknown tool: " + method)

func operation_result(id: String) -> Dictionary:
	var value: Dictionary = operation_records.get_result(id)
	if not value.has("error") and value.tool == "apply_script_changes":
		value.current_resume = documents.operations.resume_availability(id)
		var uris: Array = []
		for record: Dictionary in value.result.get("documents", []):
			if str(record.uri).get_extension() in ["gd", "gdshader"]: uris.append(record.uri)
		value.current_runtime = runtime.source_state(uris)
		value.undo_steps = []
		for step: Dictionary in value.result.get("undo", {}).get("steps", []): value.undo_steps.append(undo_availability(step.edit_id))
	if not value.has("error") and value.result.has("deletion_id"):
		var record: Dictionary = assets.deletions.recovery.read_record(value.result.deletion_id)
		value.current_recovery = record if record.has("error") else assets.deletions.recovery.summary(record)
	return value

func fail(code: String, message: String, details: Dictionary = {}) -> Dictionary:
	return {"error": {"code": code, "message": message, "details": details}}

func context(p: Dictionary) -> Dictionary:
	if p.get("scope", "") == "progress": return progress()
	var selected: Array = []
	for node: Node in EditorInterface.get_selection().get_selected_nodes():
		selected.append(node_ref(node))
	var root := EditorInterface.get_edited_scene_root()
	var data: Dictionary = {"project": ProjectSettings.globalize_path("res://"), "engine": Engine.get_version_info(), "version": Version.PRODUCT, "protocol": Version.PROTOCOL, "editor_epoch": epoch, "active_scene": root.scene_file_path if root else null, "selected_nodes": selected, "unsaved_scenes": EditorInterface.get_unsaved_scenes(), "unsaved_scripts": EditorInterface.get_script_editor().get_unsaved_files(), "unsaved_resources": dirty_resources(), "running": EditorInterface.is_playing_scene(), "run_id": runtime.run_id, "runtime_connected": runtime.ready, "debugger": debugger.state()}
	var scope: String = p.get("scope", "all")
	data.active_operation = progress().active_operation
	data.pending_operations = assets.imports.pending()
	data.pending_operations.append_array(documents.operations.pending())
	data.pending_operations.append_array(documents.diagnostics.pending())
	data.pending_operations.append_array(assets.deletions.pending())
	var filesystem := EditorInterface.get_resource_filesystem()
	data.filesystem = {"scanning": filesystem.is_scanning(), "importing": filesystem.is_importing()}
	data.recoverable_deletions = assets.deletions.recovery.list_records()
	data.last_save = documents.last_save()
	data.editor_windows = runtime.editor_captures.windows()
	data.main_screen = main_screen
	if scope == "project":
		return {"project": data.project, "engine": data.engine, "version": data.version, "protocol": data.protocol, "recoverable_deletions": data.recoverable_deletions, "last_save": data.last_save}
	if scope == "runtime":
		return {"running": data.running, "run_id": data.run_id, "runtime_connected": data.runtime_connected, "debugger": data.debugger}
	return data

func paths_safe(value: Variant) -> bool:
	if value is Dictionary:
		for child: Variant in value.values():
			if not paths_safe(child): return false
	elif value is Array:
		for child: Variant in value:
			if not paths_safe(child): return false
	elif value is String and value.begins_with("res://"):
		var relative: String = value.trim_prefix("res://")
		if relative.contains("\\") or ".." in relative.split("/") or relative.begins_with("/"): return false
		var directory: String = "res://"
		for part: String in relative.split("/"):
			var access := DirAccess.open(directory)
			if access and access.is_link(part): return false
			directory = directory.path_join(part)
	return true

func scene_root(uri: String = "") -> Node:
	return scene_access.find(uri)

func resolve_node(ref: Dictionary) -> Node:
	var root := scene_root(str(ref.get("scene", "")))
	var path: String = str(ref.get("path", "."))
	if not root or path.begins_with("/") or ".." in path.split("/") or path.contains(":"):
		return null
	return root.get_node_or_null(NodePath(path))

func node_ref(node: Node) -> Dictionary:
	if not is_instance_valid(node): return {"scene": "", "path": "", "unavailable": true}
	for root: Node in EditorInterface.get_open_scene_roots():
		if is_instance_valid(root) and (node == root or root.is_ancestor_of(node)):
			return {"scene": root.scene_file_path, "path": str(root.get_path_to(node))}
	return {"scene": "", "path": str(node.name)}

func register_resource(resource: Resource) -> String:
	var uri: String = resource.resource_path
	if uri.is_empty() or not uri.begins_with("res://"):
		uri = "godot://resources/" + epoch + "/" + str(resource.get_instance_id())
	resources[uri] = resource
	return uri

func resource_uri(uri: String) -> Resource:
	if resources.has(uri):
		return resources[uri]
	if uri.begins_with("res://") and paths_safe(uri) and ResourceLoader.exists(uri):
		var resource: Resource = load(uri)
		register_resource(resource)
		return resource
	return null

func resolve_resource(target: Dictionary) -> Resource:
	return resolve_resource_target(target).get("resource") as Resource

func resolve_resource_target(target: Dictionary, scope: String = "", expected_class: String = "Resource") -> Dictionary:
	return resource_targets.resolve(target, scope, expected_class)

func resolve_scoped_resource_target(target: Dictionary, expected_class: String = "Resource") -> Dictionary:
	var selected: Dictionary = select_case(target, ["local", "shared"], "target")
	if selected.has("error"): return selected
	var selector: Dictionary = {"node": selected.value} if selected.kind == "local" else selected.value
	return resource_targets.resolve(selector, selected.kind, expected_class)

func select_case(value: Variant, names: Array, field: String) -> Dictionary:
	if not value is Dictionary or value.size() != 1:
		return fail("INVALID_ARGUMENT", field + " must select exactly one of: " + ", ".join(names))
	var kind: String = str(value.keys()[0])
	if kind not in names or not value[kind] is Dictionary:
		return fail("INVALID_ARGUMENT", field + " requires a named object payload: " + ", ".join(names))
	return {"kind": kind, "value": value[kind]}

func encode(value: Variant) -> Variant:
	return Codec.encode(value, register_resource)

func decode(value: Variant) -> Variant:
	return Codec.decode(value, resource_uri)

func dirty_resources() -> Array:
	var values: Array = []
	for uri: String in resources:
		if documents.resource_storage(resources[uri]) != "imported" and EditorInterface.is_object_edited(resources[uri]):
			values.append(uri)
	return values

func property_info(object: Object, property: String) -> Dictionary:
	return property_edits.info(object, property)

func plan_property_changes(object: Object, values: Dictionary) -> Dictionary:
	return property_edits.plan(object, values)

func property_error(object: Object, values: Dictionary) -> String:
	return str(plan_property_changes(object, values).get("error", {}).get("message", ""))

func begin_edit(label: String, context_object: Object) -> void:
	get_undo_redo().create_action("MCP: " + label, UndoRedo.MERGE_DISABLE, context_object)
	edit_parent = {"id": null}
	if not edits.is_empty() and editor_undo.matches(edits.back()): edit_parent.id = edits.back().edit_id

func add_changes(changes: Array) -> void:
	for change: Dictionary in changes:
		get_undo_redo().add_do_property(change.object, change.property, change.after)
		get_undo_redo().add_undo_property(change.object, change.property, change.before)
		if change.object is Resource:
			get_undo_redo().add_do_method(change.object, "emit_changed")
			get_undo_redo().add_undo_method(change.object, "emit_changed")
		get_undo_redo().add_do_method(EditorInterface, "set_object_edited", change.object, true)
		get_undo_redo().add_undo_method(EditorInterface, "set_object_edited", change.object, true)

func finish_edit(context_object: Object, label: String, guards: Array = [], execute: bool = true) -> Dictionary:
	get_undo_redo().commit_action(execute)
	var history_id: int = get_undo_redo().get_object_history_id(context_object)
	var history := get_undo_redo().get_history_undo_redo(history_id)
	var edit: Dictionary = {"edit_id": "edit-" + epoch + "-" + str(Time.get_ticks_usec()), "history_id": history_id, "history_version": history.get_version(), "label": label, "guards": guards, "parent_edit_id": edit_parent.get("id")}
	edit.scene = node_ref(context_object).scene if context_object is Node else ""
	edit.editor_revision = editor_undo.revision
	edits.append(edit)
	edit_parent = {}
	if edits.size() > 100: edits.pop_front()
	return {"edit_id": edit.edit_id, "saved": false}

func commit_changes(changes: Array, context_object: Object, label: String) -> Dictionary:
	if changes.is_empty(): return {"changed": false, "saved": false}
	begin_edit(label, context_object)
	add_changes(changes)
	return finish_edit(context_object, label)

func _undo_error(edit_id: Variant) -> Dictionary:
	if edits.is_empty(): return fail("NO_EDIT", "No recorded MCP edit to undo.")
	var edit: Dictionary = edits.back()
	if edit.edit_id != edit_id: return fail("STALE_EDIT", "Only the most recent MCP edit is eligible for undo.")
	if not editor_undo.matches(edit): return fail("EDIT_CONFLICT", "Another editor action changed the native Undo order.")
	var history := get_undo_redo().get_history_undo_redo(edit.history_id)
	if not history or history.get_version() != edit.history_version:
		return fail("EDIT_CONFLICT", "Editor history changed after this MCP edit.")
	for guard: Dictionary in edit.guards:
		if not guard.check.call(): return fail("EDIT_CONFLICT", "A document changed after this MCP edit.")
	return {}

func undo_edit(p: Dictionary) -> Dictionary:
	var error: Dictionary = _undo_error(p.get("edit_id"))
	if not error.is_empty(): return error
	var edit: Dictionary = edits.back()
	var previous: Dictionary = await scene_access.enter({"scene": edit.scene}) if not edit.get("scene", "").is_empty() else {}
	if previous.has("error"): return previous
	error = _undo_error(p.get("edit_id"))
	if not error.is_empty():
		await scene_access.leave(previous)
		return error
	var history := get_undo_redo().get_history_undo_redo(edit.history_id)
	var applied: Dictionary = editor_undo.undo(edit)
	if applied.has("error"):
		await scene_access.leave(previous)
		return applied
	edits.pop_back()
	# Only a proven direct MCP predecessor may follow the version change from
	# undoing this action. Never retag across an intervening user edit.
	if not edits.is_empty() and edit.get("parent_edit_id") == edits.back().edit_id:
		edits.back().editor_revision = editor_undo.revision
		if edits.back().history_id == edit.history_id: edits.back().history_version = history.get_version()
	if edit.has("undo_result"):
		var result: Dictionary = edit.undo_result.call()
		result.undo_of = edit.edit_id
		await scene_access.leave(previous)
		return result
	await scene_access.leave(previous)
	return {"undone": edit.edit_id, "label": edit.label, "saved": false}

func undo_availability(edit_id: Variant) -> Dictionary:
	var result: Dictionary = {"edit_id": edit_id, "available": false}
	if edit_id == null:
		result.reason = "No editor undo was registered."
		return result
	var error: Dictionary = _undo_error(edit_id)
	if not error.is_empty():
		result.reason = error.error.message
		return result
	result.available = true
	return result
