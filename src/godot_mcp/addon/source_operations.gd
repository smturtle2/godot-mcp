@tool
extends RefCounted
## Source changes own their continuation; result records contain no executable state.
const DocumentResult = preload("res://addons/godot_mcp/document_result.gd")
const MAX_OPERATIONS := 32
var host: EditorPlugin
var documents: RefCounted:
	get: return host.documents
var jobs: Dictionary = {}
var stopped: bool = false

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func shutdown() -> void:
	stopped = true
	jobs.clear()

func pending() -> Array:
	var result: Array = []
	for id: String in jobs:
		result.append({"operation_id": id, "phase": jobs[id].phase, "running": jobs[id].running, "resumable": not jobs[id].running})
	return result

func resume_availability(id: String) -> Dictionary:
	return {"available": jobs.has(id) and not jobs[id].running, "running": jobs.has(id) and jobs[id].running}

func _prune() -> void:
	for id: String in jobs.keys():
		if not jobs[id].running and not host.operation_records.records.has(id): jobs.erase(id)
	while jobs.size() >= MAX_OPERATIONS:
		var removed: bool = false
		for id: String in jobs:
			if not jobs[id].running:
				jobs.erase(id)
				removed = true
				break
		if not removed: break

func _capture_bindings(p: Dictionary) -> Dictionary:
	var bindings: Array = []
	var targets: Dictionary = {}
	for attachment: Dictionary in p.get("attachments", []):
		var selected: Dictionary = host.select_case(attachment, ["script", "shader"], "attachments")
		if selected.has("error"): return selected
		var value: Dictionary = selected.value
		var record: Dictionary = {"kind": selected.kind, "arguments": value.duplicate(true), "done": false}
		var identity: String
		if selected.kind == "script":
			var node: Node = host.resolve_node(value.get("node", {}))
			if not node: return host.fail("NODE_NOT_FOUND", "Script attachment node does not exist.", {"node": value.get("node", {})})
			if not str(value.get("uri", "")).ends_with(".gd"): return host.fail("UNSUPPORTED_LANGUAGE", "Script attachments require a .gd source.")
			record.target = weakref(node)
			record.before = node.get_script()
			record.save_uri = value.node.scene
			identity = "script:" + str(node.get_instance_id())
		else:
			if not str(value.get("uri", "")).ends_with(".gdshader"): return host.fail("UNSUPPORTED_LANGUAGE", "Shader attachments require a .gdshader source.")
			var target: Dictionary = host.resolve_scoped_resource_target(value.get("target", {}), "ShaderMaterial")
			if target.has("error"): return target
			record.target = weakref(target.resource)
			record.before = target.resource.shader
			record.save_uri = target.get("scene", host.register_resource(target.resource))
			identity = "shader:" + JSON.stringify(value.target)
		if targets.has(identity): return host.fail("DUPLICATE_ATTACHMENT", "Attach each source target once per change bundle.")
		targets[identity] = true
		bindings.append(record)
	for kind: String in ["connect", "disconnect"]:
		for connection: Dictionary in p.get("connections", {}).get(kind, []):
			var from: Node = host.resolve_node(connection.get("from", {}))
			var to: Node = host.resolve_node(connection.get("to", {}))
			if not from or not to: return host.fail("NODE_NOT_FOUND", "Signal endpoints must exist before the source bundle is applied.")
			if connection.from.scene != connection.to.scene: return host.fail("CROSS_SCENE", "A persistent signal connection must belong to one scene.")
			var callable: Callable = _connection_callable(connection, to)
			var connected: bool = from.has_signal(connection.signal) and from.is_connected(connection.signal, callable)
			var identity: String = "signal:" + JSON.stringify(connection)
			if targets.has(identity): return host.fail("DUPLICATE_CONNECTION", "Change each signal connection once per bundle.")
			targets[identity] = true
			bindings.append({"kind": kind, "arguments": connection.duplicate(true), "from": weakref(from), "to": weakref(to), "before": connected, "done": false, "save_uri": connection.from.scene})
	return {"bindings": bindings}

func _connection_callable(connection: Dictionary, to: Node) -> Callable:
	var callable := Callable(to, connection.method)
	var binds: Array = []
	for value: Variant in connection.get("binds", []): binds.append(host.decode(value))
	if not binds.is_empty(): callable = callable.bindv(binds)
	return callable

func _guard_binding(binding: Dictionary) -> Dictionary:
	var value: Dictionary = binding.arguments
	if binding.kind == "script":
		var node: Node = host.resolve_node(value.node)
		if not node or node != binding.target.get_ref() or node.get_script() != binding.before:
			return host.fail("ATTACHMENT_CONFLICT", "The script attachment target changed after this bundle was prepared.", {"node": value.node})
	elif binding.kind == "shader":
		var target: Dictionary = host.resolve_scoped_resource_target(value.target, "ShaderMaterial")
		if target.has("error"): return target
		if target.resource != binding.target.get_ref() or target.resource.shader != binding.before:
			return host.fail("ATTACHMENT_CONFLICT", "The shader attachment target changed after this bundle was prepared.", {"target": value.target})
	else:
		var from: Node = host.resolve_node(value.from)
		var to: Node = host.resolve_node(value.to)
		if not from or not to or from != binding.from.get_ref() or to != binding.to.get_ref():
			return host.fail("CONNECTION_CONFLICT", "A signal endpoint changed after this bundle was prepared.")
		var current: bool = from.has_signal(value.signal) and from.is_connected(value.signal, _connection_callable(value, to))
		if current != binding.before: return host.fail("CONNECTION_CONFLICT", "The signal connection changed after this bundle was prepared.")
	return {}

func _guard_sources(job: Dictionary) -> Dictionary:
	for uri: String in job.revisions:
		var info: Dictionary = documents.source_info(uri)
		if info.has("error"): return info
		if info.external_change or info.revision != job.revisions[uri]:
			return host.fail("SOURCE_CHANGED", "Source changed after this bundle was applied. Read current sources; resume with their revisions to accept repaired text.", {"uri": uri, "expected_revision": job.revisions[uri], "current_revision": info.revision, "conflict": info.conflict})
	return {}

func _guard_validated(job: Dictionary) -> Dictionary:
	var guard: Dictionary = _guard_sources(job)
	if not guard.is_empty(): return guard
	var proof: Dictionary = documents.validation_current(job.get("validation_proof", {}))
	if not proof.current: return host.fail("VALIDATION_STALE", str(proof.reason), {"operation_id": job.id})
	return {}

func start(p: Dictionary) -> Dictionary:
	if p.get("editor_epoch", "") != host.epoch: return host.fail("EDITOR_RESTARTED", "Read current sources after the editor restart.")
	_prune()
	if jobs.size() >= MAX_OPERATIONS: return host.fail("OPERATION_LIMIT", "All source operation slots are running; wait for a result.")
	var plans: Array = p.get("documents", [])
	if plans.is_empty() or plans.size() > 100: return host.fail("INVALID_ARGUMENT", "Provide a non-empty bounded source plan.")
	var seen: Dictionary = {}
	var bytes: int = 0
	for plan: Dictionary in plans:
		var uri: String = str(plan.get("uri", ""))
		if seen.has(uri): return host.fail("DUPLICATE_DOCUMENT", "Combine changes for each URI.")
		seen[uri] = true
		if not uri.begins_with("res://") or uri.get_extension() not in ["gd", "gdshader"]: return host.fail("UNSUPPORTED_LANGUAGE", "Use .gd or .gdshader source paths.")
		var source_bytes: int = str(plan.get("source", "")).to_utf8_buffer().size()
		bytes += source_bytes
		if source_bytes > 1000000 or bytes > 8 * 1024 * 1024: return host.fail("SOURCE_LIMIT", "Source plans are limited to 1,000,000 bytes per source and 8 MiB total.")
		for other: Dictionary in jobs.values():
			if other.running and other.revisions.has(uri): return host.fail("SOURCE_BUSY", "This source has a running change operation. Wait for its result before applying another patch.", {"uri": uri, "operation_id": other.id})
		var info: Dictionary = documents.source_info(uri)
		if plan.get("create", false):
			if not info.has("error"): return host.fail("ALREADY_EXISTS", "The source or draft now exists.", {"uri": uri})
			if info.error.code != "FILE_NOT_FOUND": return info
			plan.before = null
		else:
			if info.has("error"): return info
			if info.external_change or info.revision != plan.get("if_revision") or info.disk_revision != plan.get("disk_revision"):
				return host.fail("REVISION_CONFLICT", "The source changed while the patch was being prepared; read it again.", {"uri": uri, "current_revision": info.revision, "disk_revision": info.disk_revision, "conflict": info.conflict})
			plan.before = info.source
	var captured: Dictionary = _capture_bindings(p)
	if captured.has("error"): return captured
	for binding: Dictionary in captured.bindings:
		if binding.kind not in ["script", "shader"]: continue
		if not seen.has(binding.arguments.uri): return host.fail("ATTACHMENT_SOURCE", "An attachment source must be included in this patch.", {"uri": binding.arguments.uri})
	var save_uris: Array = seen.keys() if p.get("save", false) else []
	for binding: Dictionary in captured.bindings:
		if p.get("save", false) and binding.save_uri not in save_uris: save_uris.append(binding.save_uri)
	var save_plan: Dictionary = documents.save_plan(save_uris) if p.get("save", false) else {"uris": [], "additional_uris": []}
	if p.get("preview", false):
		var preview: Array = []
		for plan: Dictionary in plans:
			preview.append({"uri": plan.uri, "effect": "created" if plan.create else "updated", "revision": str(plan.source).sha256_text(), "current_revision": plan.get("if_revision"), "merged": plan.get("merged", false), "source": plan.source})
		return {"preview": true, "documents": preview, "save_plan": save_plan, "attachments": p.get("attachments", []), "connections": p.get("connections", {}), "validation": "not_run", "editor_epoch": host.epoch}
	if not save_plan.additional_uris.is_empty(): return host.fail("SAVE_SCOPE_REQUIRED", "Saving this bundle's scene may persist other edited documents. Save or reconcile the additional documents explicitly first.", {"save_plan": save_plan})
	# Obtain every existing resource before creating drafts or committing an Undo.
	for plan: Dictionary in plans:
		if not plan.create:
			plan.resource = documents.store.ensure_resource(plan.uri)
			if not plan.resource: return host.fail("SOURCE_UNAVAILABLE", "Cannot obtain the live source resource.", {"uri": plan.uri})
	var reservation: Dictionary = host.operation_records.begin("apply_script_changes")
	if reservation.has("error"): return reservation
	for plan: Dictionary in plans:
		if plan.create:
			plan.resource = GDScript.new() if plan.uri.ends_with(".gd") else Shader.new()
			plan.resource.resource_path = plan.uri
			host.register_resource(plan.resource)
	var context: Resource = plans[0].resource
	host.begin_edit("Edit source documents", context)
	var undo: EditorUndoRedoManager = host.get_undo_redo()
	var guards: Array = []
	var revisions: Dictionary = {}
	for plan: Dictionary in plans:
		undo.add_do_method(documents.store, "set_source", plan.uri, plan.source, plan.resource)
		undo.add_undo_method(documents.store, "restore_source", plan.uri, plan.before)
		revisions[plan.uri] = str(plan.source).sha256_text()
		guards.append({"check": documents.store.source_matches.bind(plan.uri, revisions[plan.uri])})
	documents.store.staging = p.get("save", false)
	var edit: Dictionary = host.finish_edit(context, "Edit source documents", guards)
	documents.store.staging = false
	var result: Dictionary = DocumentResult.begin({"edit_id": edit.edit_id, "scope": ["live_sources"], "retained_files": [], "steps": [{"edit_id": edit.edit_id, "scope": "live_sources"}], "note": "Undo steps run newest first and preserve saved disk files; user changes can make a step unavailable."})
	result.operation_id = reservation.operation_id
	result.attachments = []
	result.connections = []
	result.phases = {"source": "applied", "save_sources": "pending" if p.get("save", false) else "not_requested", "validation": "pending", "editor_reload": "pending", "bindings": "pending" if not captured.bindings.is_empty() else "not_requested", "save_bindings": "pending" if p.get("save", false) and not captured.bindings.is_empty() else "not_requested"}
	result.runtime = {"state": "unverified", "reason": "Source application and editor reload do not verify a running game's behavior."}
	var job: Dictionary = {"id": reservation.operation_id, "plans": plans, "revisions": revisions, "applied_revisions": revisions.duplicate(), "bindings": captured.bindings, "save": p.get("save", false), "result": result, "validation": {}, "reload": {}, "saves": {}, "running": true, "reload_mode": p.get("reload", "auto"), "phase": "save_sources" if p.get("save", false) else "validation", "attempts": []}
	jobs[job.id] = job
	_publish(job, true)
	# Retain the receipt first, then finish source persistence under this request's
	# existing gate. No frame or deferred continuation exposes half of the bundle.
	if job.save:
		if not await _save(job, job.revisions.keys(), "save_sources", true): return job.result.duplicate(true)
		job.phase = "validation"
		_publish(job, true)
	_advance.call_deferred(job.id)
	return result.duplicate(true)

func resume(p: Dictionary) -> Dictionary:
	var id: String = str(p.get("operation_id", ""))
	if not jobs.has(id): return host.fail("OPERATION_NOT_RESUMABLE", "This source operation has completed or its continuation expired. Inspect its retained result.", {"operation_id": id})
	var job: Dictionary = jobs[id]
	if job.running: return job.result.duplicate(true)
	job.reload_mode = p.get("reload", "auto")
	if not host.operation_records.records.has(id):
		jobs.erase(id)
		return host.fail("OPERATION_RESULT_EXPIRED", "The retained source operation expired; its continuation was discarded.", {"operation_id": id})
	if p.has("revisions"):
		var accepted: Dictionary = p.revisions
		if accepted.size() != job.revisions.size(): return host.fail("REVISION_CONFLICT", "Resume revisions must include every source in the original bundle.")
		for uri: String in job.revisions:
			var info: Dictionary = documents.source_info(uri)
			if info.has("error"): return info
			if info.external_change or accepted.get(uri) != info.revision: return host.fail("REVISION_CONFLICT", "Resume requires the current revision of every source.", {"uri": uri, "current_revision": info.revision})
		job.revisions = accepted.duplicate()
		job.validation.clear()
		job.reload.clear()
		job.phase = "save_sources" if job.save else "validation"
	var guard: Dictionary = _guard_sources(job)
	if not guard.is_empty(): return guard
	for binding: Dictionary in job.bindings:
		if not binding.done:
			var binding_guard: Dictionary = _guard_binding(binding)
			if not binding_guard.is_empty(): return binding_guard
	job.attempts.append({"phase": job.phase, "failures": job.result.failures.duplicate(true), "at_usec": Time.get_ticks_usec()})
	# Recheck dependency validity and reload after a pause, even if only a
	# dependency/save state changed. Completed binding steps remain completed.
	job.validation.clear()
	job.reload.clear()
	job.phase = "save_sources" if job.save else "validation"
	job.result.phases.validation = "pending"
	job.result.phases.editor_reload = "pending"
	if job.attempts.size() > 16: job.attempts.pop_front()
	job.result.failures = []
	job.running = true
	_publish(job, true)
	_advance.call_deferred(id)
	return job.result.duplicate(true)

func _refresh(job: Dictionary) -> void:
	job.result.phases.source = "staged" if documents.store.has_pending_sources(job.revisions.keys()) else "applied"
	job.result.runtime = host.runtime.source_state(job.revisions.keys())
	var records: Array = []
	for plan: Dictionary in job.plans:
		var record: Dictionary = DocumentResult.document(documents.document_state(plan.uri), "created" if plan.create else "updated")
		if record.get("revision") != job.applied_revisions[plan.uri]: record.applied_revision = job.applied_revisions[plan.uri]
		record.merged = plan.get("merged", false)
		if job.saves.has(plan.uri): record.save = job.saves[plan.uri].duplicate(true)
		record.live_reload = job.reload.get(plan.uri, "not_attempted")
		if job.validation.has(plan.uri): DocumentResult.validation(record, job.validation[plan.uri])
		else: record.validation = {"state": "pending", "scope": "snapshot", "revision": job.revisions[plan.uri], "entries": []}
		records.append(record)
	for record: Dictionary in job.result.documents:
		if not job.revisions.has(record.uri): records.append(record)
	job.result.documents = records
	job.result.attempts = job.attempts.duplicate(true)
	job.result.pending_save = []
	for binding: Dictionary in job.bindings:
		if binding.done and binding.save_uri not in job.result.pending_save and job.result.phases.save_bindings != "completed": job.result.pending_save.append(binding.save_uri)
	DocumentResult.finish(job.result, true)

func _publish(job: Dictionary, running: bool) -> void:
	_refresh(job)
	job.result.resumable = not running and not job.result.failures.is_empty()
	job.result.phase = job.phase
	if running:
		job.result.status = "pending"
		job.result.complete = false
		job.result.pending = [job.phase]
	elif not job.result.failures.is_empty():
		job.result.pending = [job.phase]
	job.result.details_retained = host.operation_records.publish(job.id, job.result, running)

func _pause(job: Dictionary, phase: String, error: Dictionary) -> void:
	job.phase = phase
	job.running = false
	job.result.phases[phase] = "blocked"
	var failure: Dictionary = error.get("error", error)
	DocumentResult.failure(job.result, phase, str(failure.get("code", "SOURCE_OPERATION_FAILED")), str(failure.get("message", "The source operation could not continue.")), {}, {"tool": "resume_script_changes", "arguments": {"operation_id": job.id}, "prerequisite": "Resolve the failure. If sources were repaired, read them and include their current revisions when resuming."}, failure.get("details", {}))
	_publish(job, false)

func _gate(job: Dictionary) -> bool:
	while host.busy and not stopped: await host.get_tree().process_frame
	if stopped: return false
	host.enter_busy("apply_script_changes", job.id, job.phase)
	return true

func _save(job: Dictionary, uris: Array, phase: String, owns_gate: bool = false) -> bool:
	if not owns_gate and not await _gate(job): return false
	if owns_gate: host.active_request.phase = phase
	var guard: Dictionary = _guard_sources(job)
	if not guard.is_empty():
		if not owns_gate: host.busy = false
		_pause(job, phase, guard)
		return false
	var result: Dictionary = await documents.save_documents({"uris": uris})
	if not owns_gate: host.busy = false
	if result.has("error"):
		_pause(job, phase, result)
		return false
	for record: Dictionary in result.documents:
		if record.has("save"): job.saves[record.uri] = record.save
		DocumentResult.put(job.result, record)
		if record.get("save", {}).get("state") == "saved" and record.uri not in job.result.undo.retained_files: job.result.undo.retained_files.append(record.uri)
	if not result.complete:
		job.result.failures.append_array(result.failures)
		_pause(job, phase, {"code": "SAVE_FAILED", "message": "Some requested documents could not be saved."})
		return false
	job.result.phases[phase] = "completed"
	return true

func _advance(id: String) -> void:
	if stopped or not jobs.has(id): return
	var job: Dictionary = jobs[id]
	if job.phase == "save_sources":
		if not await _save(job, job.revisions.keys(), "save_sources"): return
		job.phase = "validation"
		_publish(job, true)
	if job.phase == "validation":
		# A compiler worker runs without holding the editor mutation gate. Its
		# complete fingerprint and source guards invalidate a concurrent edit.
		var guard: Dictionary = _guard_sources(job)
		if not guard.is_empty():
			_pause(job, "validation", guard)
			return
		var checked: Dictionary = await documents.validate_sources(job.revisions.keys())
		if stopped: return
		if checked.has("error"):
			_pause(job, "validation", checked)
			return
		job.validation.clear()
		job.validation_proof = checked.get("proof", {})
		var valid: bool = true
		for source: Dictionary in checked.sources:
			job.validation[source.uri] = source
			if source.get("state") != "valid": valid = false
		if checked.has("snapshot_id"): job.result.validation_snapshot = checked.snapshot_id
		if not valid:
			_pause(job, "validation", {"code": "VALIDATION_BLOCKED", "message": "Current sources must have a fresh valid snapshot before bindings or editor reload can proceed."})
			return
		job.result.phases.validation = "completed"
		job.phase = "editor_reload"
		_publish(job, true)
	if job.phase == "editor_reload":
		if job.get("reload_mode", "auto") == "defer":
			for uri: String in job.revisions: job.reload[uri] = "deferred"
			_pause(job, "editor_reload", {"code": "RELOAD_DEFERRED", "message": "Explicit editor reload was deferred. Saved files remain saved; Godot may still reload automatically. Resume with reload=auto when ready."})
			return
		if not await _gate(job): return
		var guard: Dictionary = _guard_validated(job)
		if not guard.is_empty():
			host.busy = false
			_pause(job, "editor_reload", guard)
			return
		for plan: Dictionary in job.plans:
			var resource: Resource = documents.store.ensure_resource(plan.uri)
			if not resource:
				host.busy = false
				_pause(job, "editor_reload", {"code": "SOURCE_UNAVAILABLE", "message": "The source resource is no longer available.", "details": {"uri": plan.uri}})
				return
			if not FileAccess.file_exists(plan.uri):
				job.reload[plan.uri] = "deferred"
			elif resource is Script:
				var reloaded: Error = resource.reload(true)
				job.reload[plan.uri] = "succeeded" if reloaded == OK else "failed"
				if reloaded != OK:
					host.busy = false
					_pause(job, "editor_reload", {"code": "LIVE_RELOAD_FAILED", "message": "The source snapshot is valid but the editor could not reload this script. Save required drafts, then resume.", "details": {"uri": plan.uri}})
					return
			elif resource is Shader:
				resource.get_rid()
				job.reload[plan.uri] = "succeeded"
		host.busy = false
		job.result.phases.editor_reload = "deferred" if "deferred" in job.reload.values() else "completed"
		job.phase = "bindings"
		_publish(job, true)
	if job.phase == "bindings":
		for binding: Dictionary in job.bindings:
			if binding.done: continue
			if not await _gate(job): return
			var guard: Dictionary = _guard_validated(job)
			if guard.is_empty(): guard = _guard_binding(binding)
			if not guard.is_empty():
				host.busy = false
				_pause(job, "bindings", guard)
				return
			if binding.kind in ["script", "shader"] and not FileAccess.file_exists(binding.arguments.uri):
				host.busy = false
				_pause(job, "bindings", {"code": "SOURCE_NOT_SAVED", "message": "Save new source dependencies before attaching them, then resume this bundle.", "details": {"uris": job.revisions.keys()}})
				return
			var applied: Dictionary = await _apply_binding(binding)
			host.busy = false
			if applied.has("error"):
				_pause(job, "bindings", applied)
				return
			binding.done = true
			if applied.get("edit_id") != null:
				job.result.undo.edit_id = applied.edit_id
				job.result.undo.scope = ["bindings"]
				job.result.undo.steps.append({"edit_id": applied.edit_id, "scope": "bindings"})
			if binding.kind in ["script", "shader"]: job.result.attachments.append({binding.kind: binding.arguments.duplicate(true)})
			else: job.result.connections.append({binding.kind: binding.arguments.duplicate(true)})
			_publish(job, true)
		job.result.phases.bindings = "completed" if not job.bindings.is_empty() else "not_requested"
		job.phase = "save_bindings"
	if job.phase == "save_bindings":
		var targets: Array = []
		for binding: Dictionary in job.bindings:
			if binding.done and binding.save_uri not in targets: targets.append(binding.save_uri)
		if job.save and not targets.is_empty():
			if not await _save(job, targets, "save_bindings"): return
		else: job.result.phases.save_bindings = "not_requested"
	job.phase = "completed"
	job.running = false
	_publish(job, false)
	jobs.erase(id)

func _apply_binding(binding: Dictionary) -> Dictionary:
	var value: Dictionary = binding.arguments
	if binding.kind == "script":
		return await host.dispatch("update_nodes", {"changes": [{"node": value.node, "set": {"script": {"$type": "Resource", "uri": value.uri}}}]})
	if binding.kind == "shader":
		return await host.dispatch("update_resource", {"target": value.target, "set": {"shader": {"$type": "Resource", "uri": value.uri}}})
	return await host.dispatch("update_signals", {binding.kind: [value]})
