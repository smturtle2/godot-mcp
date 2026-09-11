@tool
extends RefCounted
## Import phases outlive a timed-out request; all writes use the editor's mutation gate.
const FileJournal = preload("res://addons/godot_mcp/file_journal.gd")
const OperationResult = preload("res://addons/godot_mcp/operation_result.gd")
var host: EditorPlugin
var files: RefCounted
var operations: Dictionary = {}
var wait_timeout_ms: int = 30000
var stopped: bool = false

func _init(editor_host: EditorPlugin, file_operations: RefCounted) -> void:
	host = editor_host
	files = file_operations

func shutdown() -> void:
	stopped = true
	# Release the assets/import manager cycle after pending waits have been stopped.
	files = null

func pending() -> Array:
	var result: Array = []
	for job: Dictionary in operations.values():
		if not job.done: result.append({"operation_id": job.id, "phase": job.phase, "paths": job.journal.paths})
	return result

func _overlap(paths: Array) -> String:
	for job: Dictionary in operations.values():
		if job.done: continue
		for path: String in paths:
			if path in job.journal.paths: return job.id
	return ""

func start(p: Dictionary) -> Dictionary:
	if files.has_unsaved_documents(): return host.fail("UNSAVED_DOCUMENTS", "Save documents before filesystem imports so undo can preserve them.")
	var staged: Dictionary = {}
	var expected: Dictionary = {}
	var paths: Array = []
	var total: int = 0
	for spec: Dictionary in p.get("files", []):
		var destination: String = str(spec.get("destination", ""))
		if not files.writable_asset(destination): return host.fail("INVALID_PATH", "Import destination must be an authored project asset.")
		if destination in paths: return host.fail("DUPLICATE_TARGET", "Each destination must occur once.")
		for path: String in [destination, destination + ".import", destination + ".uid"]:
			if not host.paths_safe(path): return host.fail("INVALID_PATH", "An import target or metadata path contains a symlink.")
			paths.append(path)
		var pending_id: String = _overlap([destination, destination + ".import", destination + ".uid"])
		if not pending_id.is_empty(): return host.fail("OPERATION_PENDING", "An import still owns these paths; query its state before retrying.", {"operation_id": pending_id})
		if spec.has("source"):
			var source: String = files.local_file(str(spec.source))
			if source.is_empty() or not FileAccess.file_exists(source): return host.fail("FILE_NOT_FOUND", "Import source is not an existing local file.")
			if FileAccess.file_exists(destination) and not spec.get("overwrite", false): return host.fail("ALREADY_EXISTS", "Set overwrite=true to replace an asset.")
			var file := FileAccess.open(source, FileAccess.READ)
			if not file: return host.fail("IMPORT_FAILED", "Cannot read the import source.")
			total += file.get_length()
			if total > 128 * 1024 * 1024: return host.fail("LIMIT_EXCEEDED", "Imports are limited to 128 MiB per transaction.")
			staged[destination] = file.get_buffer(file.get_length())
			expected[destination] = staged[destination]
		elif not FileAccess.file_exists(destination): return host.fail("FILE_NOT_FOUND", "Reimport destination does not exist.")
		else: expected[destination] = FileAccess.get_file_as_bytes(destination)
	if paths.is_empty(): return host.fail("EMPTY_IMPORT", "Provide at least one asset.")
	if operations.size() >= 32: return host.fail("LIMIT_EXCEEDED", "Too many imports are still pending.")
	var reservation: Dictionary = host.operation_records.begin("import_assets")
	if reservation.has("error"): return reservation
	var id: String = reservation.operation_id
	var job: Dictionary = {"id": id, "phase": "writing", "specs": p.files.duplicate(true), "journal": FileJournal.new(paths), "expected": expected, "files_written": [], "options_changed": [], "failures": [], "done": false, "monitoring": false, "conflicted": false, "edit_id": null, "assets": []}
	operations[id] = job
	if files.write_files(staged):
		job.files_written = staged.keys()
		job.phase = "importing"
	else:
		for path: String in job.journal.changed_paths():
			if staged.has(path): job.files_written.append(path)
		# Keep the actual state left by a partial write as the continuation guard.
		# The requested bytes may never have reached every destination.
		job.expected = FileJournal.snapshot(expected.keys())
		job.failures.append(OperationResult.failure("writing", {"code": "IMPORT_FAILED", "message": "Some import files could not be written; inspect the retained changes."}))
		job.phase = "settling"
		EditorInterface.get_resource_filesystem().scan()
	await _advance(job)
	if not job.done: _schedule(job)
	var result: Dictionary = _result(job)
	result.details_retained = host.operation_records.publish(id, result, not job.done)
	if job.done: operations.erase(id)
	return result

func _sources_match(job: Dictionary) -> bool:
	if FileJournal.matches(job.expected): return true
	job.conflicted = true
	job.failures.append(OperationResult.failure(job.phase, {"code": "IMPORT_CONFLICT", "message": "An asset source changed while import was in progress. Automatic continuation and undo are unavailable; inspect the affected paths."}))
	job.done = true
	job.phase = "failed"
	return false

func _apply_options(job: Dictionary) -> void:
	var prepared: Array = []
	var reimports := PackedStringArray()
	# Validate every options file/key before applying any option changes.
	for spec: Dictionary in job.specs:
		var destination: String = spec.destination
		if not spec.get("options", {}).is_empty():
			var config := ConfigFile.new()
			if config.load(destination + ".import") != OK:
				job.failures.append(OperationResult.failure("options", {"code": "IMPORT_OPTIONS_UNAVAILABLE", "message": "This asset has no import options file: " + destination}))
				return
			var changed: bool = false
			for key: String in spec.options:
				if not config.has_section_key("params", key):
					job.failures.append(OperationResult.failure("options", {"code": "INVALID_IMPORT_OPTION", "message": "Unknown import option: " + key, "details": {"uri": destination}}))
					return
				var value: Variant = host.decode(spec.options[key])
				if value != config.get_value("params", key): changed = true
				config.set_value("params", key, value)
			if changed: prepared.append({"uri": destination + ".import", "config": config})
		if FileAccess.file_exists(destination + ".import"): reimports.append(destination)
	for item: Dictionary in prepared:
		var error: Error = item.config.save(item.uri)
		if error != OK:
			job.failures.append(OperationResult.failure("options", {"code": "IMPORT_OPTIONS_FAILED", "message": "Cannot save import options: " + item.uri, "details": {"error": error_string(error)}}))
			return
		job.options_changed.append(item.uri)
	if not reimports.is_empty(): EditorInterface.get_resource_filesystem().reimport_files(reimports)

func _advance(job: Dictionary) -> void:
	if job.done or stopped: return
	if not await files.wait_import(wait_timeout_ms): return
	if stopped: return
	if job.phase == "importing":
		if not _sources_match(job): return
		_apply_options(job)
		job.phase = "reimporting" if job.failures.is_empty() else "settling"
		if not await files.wait_import(wait_timeout_ms): return
	if stopped: return
	if not _sources_match(job): return
	job.journal.finalize()
	if not job.journal.changed_paths().is_empty():
		var edit: Dictionary = files.record_files(job.journal.before, job.journal.after, "Import assets")
		job.edit_id = edit.get("edit_id")
	for spec: Dictionary in job.specs:
		var resource: Resource = host.resource_uri(spec.destination)
		job.assets.append({"uri": spec.destination, "imported": resource != null, "resource": host.encode(resource), "preservation": "Author-created external resources and scene overrides remain separate; edits inside regenerated imported data are not preserved."})
		if not resource and job.failures.is_empty(): job.failures.append(OperationResult.failure("resolve", {"code": "IMPORT_UNAVAILABLE", "message": "The copied asset is not available as a Godot resource: " + spec.destination}))
	job.done = true
	job.phase = "completed" if job.failures.is_empty() else "failed"

func _schedule(job: Dictionary) -> void:
	if job.monitoring or stopped: return
	job.monitoring = true
	_resume.call_deferred(str(job.id))

func _resume(id: String) -> void:
	var job: Dictionary = operations[id]
	while not stopped and not job.done:
		# Waiting for importer quiescence does not hold the mutation gate. Acquire
		# it before options, undo registration or another stage can change state.
		if not await files.wait_import(wait_timeout_ms): continue
		while not stopped and host.busy: await host.get_tree().process_frame
		if stopped: break
		host.enter_busy("import_assets", job.id, job.phase)
		await _advance(job)
		host.operation_records.publish(job.id, _result(job), not job.done)
		host.busy = false
	job.monitoring = false
	if job.done: operations.erase(id)

func _result(job: Dictionary) -> Dictionary:
	var failures: Array = job.failures.duplicate(true)
	var pending_stages: Array = [] if job.done else [job.phase]
	if not job.done: failures.append(OperationResult.failure(job.phase, {"code": "IMPORT_TIMEOUT", "message": "Godot import is still pending; query this operation ID instead of importing the same paths again."}))
	var changed: Array = job.journal.changed_paths()
	var undo_state: String = "pending" if not job.done else ("unavailable" if job.conflicted else ("available" if job.edit_id != null else "not_needed"))
	var result: Dictionary = {"operation_id": job.id, "phase": job.phase, "saved": not job.files_written.is_empty() or not job.options_changed.is_empty(), "files_written": job.files_written.duplicate(), "options_changed": job.options_changed.duplicate(), "changed_paths": changed, "assets": job.assets.duplicate(true), "edit_id": job.edit_id, "undo_state": undo_state, "undo": {"edit_id": job.edit_id, "scope": ["files"] if job.edit_id != null else [], "note": "Undo is registered only after the importer is quiet and checks the finalized files and editor history. Operation records live in this editor session."}}
	return OperationResult.finish(result, not changed.is_empty() or not job.files_written.is_empty() or not job.options_changed.is_empty(), failures, pending_stages)
