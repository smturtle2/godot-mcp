@tool
extends RefCounted
## Preview owns intent; the durable recovery record owns bytes; operation records own receipts.
const Recovery = preload("res://addons/godot_mcp/asset_recovery.gd")
var host: EditorPlugin
var recovery: RefCounted
var plans: Dictionary = {}
var jobs: Dictionary = {}
var identities: Dictionary = {}
var undo_results: Dictionary = {}
var redo_plans: Dictionary = {}
var stopped: bool = false

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host
	recovery = Recovery.new(host)

func shutdown() -> void:
	stopped = true
	identities.clear()

func pending() -> Array:
	var result: Array = []
	for job: Dictionary in jobs.values():
		result.append({"operation_id": job.operation_id, "phase": "editor_sync", "paths": job.applied})
	return result

func _idle_error() -> Dictionary:
	if EditorInterface.is_playing_scene(): return host.fail("GAME_RUNNING", "Stop the running game before changing project files.")
	var fs := EditorInterface.get_resource_filesystem()
	if fs.is_scanning() or fs.is_importing() or not jobs.is_empty() or not host.assets.imports.pending().is_empty() or not host.documents.operations.pending().is_empty():
		return host.fail("OPERATION_PENDING", "Wait for pending source and filesystem operations before changing assets.")
	return {}

func writable(uri: String) -> bool:
	if not uri.begins_with("res://") or uri in ["res://", "res:/"] or not host.paths_safe(uri): return false
	if uri.simplify_path().trim_suffix("/") != uri: return false
	var relative: String = uri.trim_prefix("res://")
	for part: String in relative.split("/"):
		if part in [".git", ".godot", ".godot-mcp"] or part.is_empty(): return false
	return uri not in ["res://project.godot", "res://export_presets.cfg", "res://export_credentials.cfg", "res://addons/godot_mcp"] and not uri.begins_with("res://addons/godot_mcp/")

func _source(uri: String) -> bool:
	return uri.get_extension() in ["gd", "gdshader"]

func _inside(uri: String, roots: Array) -> bool:
	for root: String in roots:
		if uri == root or uri.begins_with(root + "/"): return true
	return false

func _block(blockers: Array, code: String, message: String, uri: String = "") -> void:
	blockers.append({"code": code, "message": message, "uri": uri})

func _entry(uri: String, kind: String) -> Dictionary:
	var entry: Dictionary = {"uri": uri, "kind": kind}
	if kind == "file":
		var file := FileAccess.open(uri, FileAccess.READ)
		if not file: return host.fail("FILE_UNREADABLE", "Cannot read a deletion target.", {"uri": uri})
		entry.size = file.get_length()
		entry.sha256 = FileAccess.get_sha256(uri)
		if entry.sha256.is_empty(): return host.fail("FILE_UNREADABLE", "Cannot fingerprint a deletion target.", {"uri": uri})
		var uid: int = ResourceUID.INVALID_ID
		if FileAccess.file_exists(uri + ".uid"): uid = ResourceUID.text_to_id(FileAccess.get_file_as_string(uri + ".uid").strip_edges())
		elif FileAccess.file_exists(uri + ".import"):
			var config := ConfigFile.new()
			if config.load(uri + ".import") == OK: uid = ResourceUID.text_to_id(str(config.get_value("remap", "uid", "")))
		elif uri.get_extension() in ["tscn", "tres", "scn", "res"]: uid = ResourceLoader.get_resource_uid(uri)
		if uid != ResourceUID.INVALID_ID:
			entry.uid = ResourceUID.id_to_text(uid)
			entry.uid_path = ResourceUID.get_id_path(uid) if ResourceUID.has_id(uid) else ""
	return entry

func _collect(options: Dictionary) -> Dictionary:
	var paths: Array = options.paths
	var pending_paths: Array = paths.duplicate()
	var entries: Dictionary = {}
	var absent: Array = []
	while not pending_paths.is_empty():
		var uri: String = str(pending_paths.pop_back()).trim_suffix("/")
		if entries.has(uri): continue
		if not writable(uri): return host.fail("INVALID_PATH", "Delete authored project assets; protected paths and symlinks cannot be deleted.", {"uri": uri})
		var kind: String = "file"
		if DirAccess.dir_exists_absolute(uri):
			kind = "directory"
			var dir := DirAccess.open(uri)
			if not dir: return host.fail("DIRECTORY_UNREADABLE", "Cannot expand a target directory.", {"uri": uri})
			for name: String in dir.get_directories(): pending_paths.append(uri.path_join(name))
			for name: String in dir.get_files(): pending_paths.append(uri.path_join(name))
		elif not FileAccess.file_exists(uri):
			if _source(uri) and host.documents.store.states.has(uri): kind = "draft"
			else: return host.fail("FILE_NOT_FOUND", "A deletion target does not exist.", {"uri": uri})
		var entry: Dictionary = _entry(uri, kind)
		if entry.has("error"): return entry
		entries[uri] = entry
		if kind != "directory" and uri.get_extension() not in ["uid", "import"]:
			for suffix: String in [".uid", ".import"]:
				var companion: String = uri + suffix
				if not writable(companion): return host.fail("INVALID_PATH", "A companion path contains a symlink.", {"uri": companion})
				if FileAccess.file_exists(companion): pending_paths.append(companion)
				else: absent.append(companion)
		if entries.size() > 20000: return host.fail("LIMIT_EXCEEDED", "One deletion plan supports at most 20000 entries.")
	# A folder may also contain source drafts that have never existed on disk.
	for uri: String in host.documents.store.states.keys():
		if _inside(uri, paths) and not entries.has(uri):
			if not writable(uri): return host.fail("INVALID_PATH", "A draft has a protected path.", {"uri": uri})
			entries[uri] = _entry(uri, "draft")
	var ordered: Array = entries.keys()
	ordered.sort()
	var result: Array = []
	for uri: String in ordered: result.append(entries[uri])
	absent.sort()
	return {"entries": result, "absent": absent}

func _plan(options: Dictionary) -> Dictionary:
	var collection: Dictionary = _collect(options)
	if collection.has("error"): return collection
	var targets: Dictionary = {}
	var blockers: Array = []
	var source_bytes: int = 0
	for entry: Dictionary in collection.entries:
		targets[entry.uri] = true
		if entry.kind != "directory" and _source(entry.uri):
			var info: Dictionary = host.documents.store.source_info(entry.uri)
			if info.has("error"): return info
			entry.revision = info.revision
			entry.unsaved = info.unsaved
			entry.base_disk_revision = info.base_disk_revision
			if info.external_change: _block(blockers, "SOURCE_CONFLICT", "The current source has an unknown or externally changed baseline.", entry.uri)
			if info.unsaved:
				if entry.uri not in options.include_unsaved: _block(blockers, "UNSAVED_SOURCE", "Include this target in include_unsaved to explicitly remove its current buffer or draft.", entry.uri)
				entry.source = info.source
				source_bytes += str(info.source).to_utf8_buffer().size()
	if source_bytes > 16 * 1024 * 1024: return host.fail("LIMIT_EXCEEDED", "A deletion plan retains at most 16 MiB of unsaved source.")
	for uri: String in options.include_unsaved:
		if not targets.has(uri) or not _source(uri): return host.fail("INVALID_UNSAVED_TARGET", "include_unsaved must name targeted .gd or .gdshader sources.", {"uri": uri})
	var impact: Dictionary = host.assets.dependencies.inspect(targets)
	if impact.has("error"): return impact
	if options.references == "block" and not impact.references.is_empty(): _block(blockers, "REFERENCES_REMAIN", "Remove the reported references or explicitly preview with references=allow_broken.")
	for uri: String in impact.affected_scenes:
		if uri.begins_with("godot://") or uri in EditorInterface.get_unsaved_scenes(): _block(blockers, "UNSAVED_SCENE", "Save the affected scene before deletion.", uri)
	for uri: String in impact.dirty_resources:
		if not targets.has(uri) or uri not in options.include_unsaved: _block(blockers, "UNSAVED_RESOURCE", "Save the affected resource before deletion.", uri)
	var dirty_sources: Array = host.documents.store.dirty_uris()
	for ref: Dictionary in impact.references:
		if ref.owner in dirty_sources: _block(blockers, "UNSAVED_REFERENCE_OWNER", "Save or remove this source reference before deletion.", ref.owner)
		if ref.owner == "res://project.godot" and impact.settings_unsaved: _block(blockers, "UNSAVED_SETTINGS", "Save affected project settings before deletion.", ref.owner)
	if not impact.coverage.skipped_large_text_files.is_empty(): _block(blockers, "REFERENCE_SCAN_INCOMPLETE", "Text files larger than 4 MiB could not be inspected; see coverage.")
	var plan: Dictionary = {"options": options.duplicate(true), "entries": collection.entries, "absent": collection.absent, "references": impact.references, "affected_scenes": impact.affected_scenes, "scene_histories": impact.scene_histories, "dirty_resources": impact.dirty_resources, "coverage": impact.coverage, "blockers": blockers}
	plan.fingerprint = JSON.stringify(plan).sha256_text()
	return plan

func _store_plan(tool: String, plan: Dictionary) -> Dictionary:
	while plans.size() >= 32: plans.erase(plans.keys()[0])
	var id: String = "asset-plan-" + host.epoch + "-" + str(Time.get_ticks_usec())
	plan.tool = tool
	plans[id] = plan
	var targets: Array = plan.get("entries", []).duplicate(true)
	for entry: Dictionary in targets: entry.erase("source")
	var result: Dictionary = {"preview": true, "plan_id": id, "tool": tool, "editor_epoch": host.epoch, "can_apply": plan.blockers.is_empty(), "targets": targets, "references": plan.get("references", []), "blockers": plan.blockers, "coverage": plan.get("coverage", {})}
	if plan.has("options"):
		result.mode = plan.options.mode
		result.options = plan.options
	result.editor_effects = {"close_scenes": plan.get("affected_scenes", []), "cache": "Detach removed resource paths and UID mappings; rescan the editor filesystem", "reference_rewrite": false}
	return result

func dispatch(method: String, p: Dictionary) -> Dictionary:
	if method == "restore_assets":
		var idle: Dictionary = _idle_error()
		return idle if not idle.is_empty() else _restore(str(p.get("deletion_id", "")), p.get("paths", []))
	var selected: Dictionary = host.select_case(p.get("action", {}), ["preview", "apply"], "action")
	if selected.has("error"): return selected
	if selected.kind == "apply": return _apply(method, str(selected.value.get("plan_id", "")))
	var idle: Dictionary = _idle_error()
	if not idle.is_empty(): return idle
	if method == "purge_deleted_assets": return _purge_preview(selected.value)
	var options: Dictionary = {"paths": selected.value.get("paths", []), "mode": selected.value.get("mode", "recoverable"), "references": selected.value.get("references", "block"), "include_unsaved": selected.value.get("include_unsaved", [])}
	if options.paths.is_empty() or options.paths.size() > 200 or options.mode not in ["recoverable", "permanent"] or options.references not in ["block", "allow_broken"]: return host.fail("INVALID_OPTIONS", "Provide paths and valid deletion options.")
	for i: int in options.paths.size(): options.paths[i] = str(options.paths[i]).trim_suffix("/")
	for uri: String in options.paths:
		if uri.get_extension() in ["uid", "import"]: return host.fail("COMPANION_TARGET", "Select the owning asset; UID and import sidecars are included automatically.", {"uri": uri})
	var plan: Dictionary = _plan(options)
	return plan if plan.has("error") else _store_plan(method, plan)

func _apply(method: String, id: String) -> Dictionary:
	if not plans.has(id) or plans[id].tool != method: return host.fail("PLAN_NOT_FOUND", "Create a fresh preview in this editor session.")
	var plan: Dictionary = plans[id]
	if plan.has("operation_id"):
		var previous: Dictionary = host.operation_records.get_result(plan.operation_id)
		return previous if previous.has("error") else previous.result
	var idle: Dictionary = _idle_error()
	if not idle.is_empty(): return idle
	if not plan.blockers.is_empty(): return host.fail("DELETE_BLOCKED", "Resolve the preview blockers and create a fresh plan.", {"blockers": plan.blockers})
	if method == "purge_deleted_assets": return _purge(plan)
	var current: Dictionary = _plan(plan.options)
	if current.has("error") or current.get("fingerprint") != plan.fingerprint: return host.fail("STALE_PLAN", "Targets, source revisions, references, or editor state changed after preview. Create a fresh preview.", {"cause": current.get("error", {})})
	return _delete(plan)

func _new_job(tool: String) -> Dictionary:
	var job: Dictionary = host.operation_records.begin(tool)
	if job.has("error"): return job
	job.merge({"action": tool, "status": "pending", "complete": false, "pending": [], "failures": [], "applied": [], "remaining": [], "edit_id": null, "editor_sync": "not_needed", "undo_state": "unavailable"})
	return job

func _failure(job: Dictionary, code: String, message: String, uri: String = "") -> void:
	job.failures.append({"phase": "filesystem", "code": code, "message": message, "details": {"uri": uri}})

func _same_file(entry: Dictionary, uri: String) -> bool:
	return host.paths_safe(uri) and FileAccess.file_exists(uri) and FileAccess.get_sha256(uri) == entry.sha256

func _close_scenes(paths: Array) -> void:
	for uri: String in paths:
		if uri in EditorInterface.get_open_scenes():
			EditorInterface.open_scene_from_path(uri)
			EditorInterface.close_scene()

func _detach(entry: Dictionary, id: String) -> void:
	var uri: String = entry.uri
	var resource: Resource = host.resources.get(uri)
	if not resource and ResourceLoader.has_cached(uri): resource = ResourceLoader.get_cached_ref(uri)
	if resource:
		if not identities.has(id): identities[id] = {}
		identities[id][uri] = resource
		EditorInterface.set_object_edited(resource, false)
	EditorInterface.get_script_editor().close_file(uri)
	if _source(uri): host.documents.store.remove_state(uri)
	for key: String in host.resources.keys():
		if key == uri or key.begins_with(uri + "::"):
			var cached: Resource = host.resources[key]
			if cached: cached.resource_path = ""
			host.resources.erase(key)
	if resource: resource.resource_path = ""
	if entry.has("uid"):
		var uid: int = ResourceUID.text_to_id(entry.uid)
		if ResourceUID.has_id(uid) and ResourceUID.get_id_path(uid) == uri: ResourceUID.remove_id(uid)

func _delete(plan: Dictionary, existing: Dictionary = {}) -> Dictionary:
	var job: Dictionary = _new_job("delete_assets")
	if job.has("error"): return job
	var record: Dictionary = recovery.create(plan) if existing.is_empty() else existing
	if record.has("error"):
		host.operation_records.discard(job.operation_id)
		return record
	job.deletion_id = record.deletion_id
	job.mode = record.mode
	job.remaining_references = plan.references
	job.coverage = plan.coverage
	plan.operation_id = job.operation_id
	if not existing.is_empty():
		record.entries = plan.entries.duplicate(true)
		record.state = "deleting"
		if recovery.save(record) != OK:
			host.operation_records.discard(job.operation_id)
			return host.fail("RECOVERY_RECORD_FAILED", "Cannot persist redo intent.")
	_close_scenes(plan.affected_scenes)
	var entries: Array = record.entries
	var directories: Array = []
	var interrupted: bool = false
	for entry: Dictionary in entries:
		var uri: String = entry.uri
		if entry.kind == "directory":
			directories.push_front(entry)
			continue
		if interrupted:
			job.remaining.append(uri)
			continue
		if entry.kind == "draft":
			entry.removed = true
			entry.restored = false
			# Persist a draft's recovery copy before clearing its only live state.
			if recovery.save(record) != OK:
				_failure(job, "RECOVERY_RECORD_FAILED", "Cannot record draft deletion.", uri)
				job.remaining.append(uri)
				interrupted = true
				continue
		else:
			if not _same_file(entry, uri):
				_failure(job, "FILE_CHANGED", "The target changed before it could be removed.", uri)
				job.remaining.append(uri)
				interrupted = true
				continue
			var error: Error
			if record.mode == "recoverable":
				var backup: String = recovery.blob(record.deletion_id, uri)
				if not host.paths_safe(backup) or FileAccess.file_exists(backup): error = ERR_ALREADY_EXISTS
				else: error = DirAccess.rename_absolute(uri, backup)
			else: error = DirAccess.remove_absolute(uri)
			if error != OK:
				_failure(job, "DELETE_FAILED", error_string(error), uri)
				job.remaining.append(uri)
				interrupted = true
				continue
			entry.removed = true
			entry.restored = false
			if record.mode == "recoverable" and not _same_file(entry, recovery.blob(record.deletion_id, uri)):
				_failure(job, "FILE_CHANGED", "The file changed during removal; its actual bytes remain in recovery and require review.", uri)
				entry.preview_sha256 = entry.sha256
				entry.sha256 = FileAccess.get_sha256(recovery.blob(record.deletion_id, uri))
				interrupted = true
		_detach(entry, record.deletion_id)
		job.applied.append(uri)
	for entry: Dictionary in directories:
		var uri: String = entry.uri
		if not interrupted and host.paths_safe(uri) and DirAccess.remove_absolute(uri) == OK:
			entry.removed = true
			entry.restored = false
			job.applied.append(uri)
		else:
			job.remaining.append(uri)
			_failure(job, "DIRECTORY_REMAINS", "The directory was retained; it may contain a failed or newly added entry.", uri)
	record.state = "deleted" if job.remaining.is_empty() else "partial"
	if recovery.save(record) != OK: _failure(job, "RECOVERY_RECORD_FAILED", "The final receipt could not be saved; recovery discovers moved files from the durable intent.")
	if existing.is_empty() and record.mode == "recoverable" and not job.applied.is_empty(): _register_undo(job, record.deletion_id)
	if record.mode == "permanent": identities.erase(record.deletion_id)
	job.recovery = recovery.summary(record)
	return _settle(job)

func _restore_selection(record: Dictionary, paths: Array) -> Array:
	var selected: Array = []
	for entry: Dictionary in record.entries:
		if not recovery.available(record, entry): continue
		var uri: String = entry.uri
		if paths.is_empty() or _inside(uri, paths) or uri.trim_suffix(".uid").trim_suffix(".import") in paths: selected.append(entry)
	return selected

func _restore_conflicts(record: Dictionary, entries: Array) -> Array:
	var conflicts: Array = []
	for entry: Dictionary in entries:
		var uri: String = entry.uri
		if not writable(uri):
			conflicts.append({"uri": uri, "reason": "Protected path or symlink"})
			continue
		if entry.kind == "directory":
			if FileAccess.file_exists(uri): conflicts.append({"uri": uri, "reason": "A file occupies the directory path"})
			continue
		if FileAccess.file_exists(uri) or DirAccess.dir_exists_absolute(uri) or host.documents.store.states.has(uri) or ResourceLoader.has_cached(uri):
			conflicts.append({"uri": uri, "reason": "A file, buffer, draft, or cached resource already occupies the path"})
		if entry.kind == "file" and not _same_file(entry, recovery.blob(record.deletion_id, uri)):
			conflicts.append({"uri": uri, "reason": "The recovery copy is missing or changed"})
		if entry.has("uid"):
			var uid: int = ResourceUID.text_to_id(entry.uid)
			if ResourceUID.has_id(uid) and ResourceUID.get_id_path(uid) != uri: conflicts.append({"uri": uri, "reason": "The UID is now owned by " + ResourceUID.get_id_path(uid)})
	return conflicts

func _restore(id: String, paths: Array = []) -> Dictionary:
	var record: Dictionary = recovery.read_record(id)
	if record.has("error"): return record
	if record.mode != "recoverable": return host.fail("PERMANENT_DELETION", "Permanent deletions do not have recovery copies.")
	var entries: Array = _restore_selection(record, paths)
	if entries.is_empty(): return host.fail("NOTHING_TO_RESTORE", "No selected recovery entries remain.")
	for uri: String in paths:
		var found: bool = false
		for entry: Dictionary in entries:
			if _inside(entry.uri, [uri]): found = true
		if not found: return host.fail("INVALID_RESTORE_PATH", "The requested path has no remaining recovery entries.", {"uri": uri})
	var conflicts: Array = _restore_conflicts(record, entries)
	if not conflicts.is_empty(): return host.fail("RESTORE_CONFLICT", "Restore would collide with current project state; no files were overwritten.", {"conflicts": conflicts})
	var job: Dictionary = _new_job("restore_assets")
	if job.has("error"): return job
	job.deletion_id = id
	job.mode = "recoverable"
	var interrupted: bool = false
	for entry: Dictionary in entries:
		var uri: String = entry.uri
		if interrupted:
			job.remaining.append(uri)
			continue
		var error: Error = OK
		if not writable(uri): error = ERR_INVALID_PARAMETER
		elif entry.kind == "directory": error = DirAccess.make_dir_recursive_absolute(uri)
		else:
			var fresh: Array = _restore_conflicts(record, [entry])
			if not fresh.is_empty(): error = ERR_ALREADY_EXISTS
			elif DirAccess.make_dir_recursive_absolute(uri.get_base_dir()) != OK: error = ERR_CANT_CREATE
			elif entry.kind == "file": error = DirAccess.rename_absolute(recovery.blob(id, uri), uri)
		if error != OK:
			_failure(job, "RESTORE_FAILED", error_string(error), uri)
			job.remaining.append(uri)
			interrupted = true
			continue
		if entry.has("uid"):
			var uid: int = ResourceUID.text_to_id(entry.uid)
			if not ResourceUID.has_id(uid): ResourceUID.add_id(uid, uri)
		var resource: Resource = identities.get(id, {}).get(uri)
		if resource:
			resource.take_over_path(uri)
			host.register_resource(resource)
		if _source(uri):
			host.documents.store.set_source(uri, entry.get("source", FileAccess.get_file_as_string(uri) if entry.kind == "file" else ""), resource)
		entry.restored = true
		entry.erase("source")
		job.applied.append(uri)
	record.state = "restored" if not recovery.summary(record).recoverable else "partial"
	if recovery.save(record) != OK: _failure(job, "RECOVERY_RECORD_FAILED", "The restore receipt could not be saved; inspect actual project paths before retrying.")
	job.recovery = recovery.summary(record)
	return _settle(job)

func can_undo(id: String) -> bool:
	if not _idle_error().is_empty(): return false
	var record: Dictionary = recovery.read_record(id)
	if record.has("error"): return false
	if record.get("undo_invalidated", false): return false
	var entries: Array = _restore_selection(record, [])
	return not entries.is_empty() and _restore_conflicts(record, entries).is_empty()

func _register_undo(job: Dictionary, id: String) -> void:
	host.begin_edit("Delete assets", ProjectSettings)
	host.get_undo_redo().add_do_method(self, "redo_delete", id)
	host.get_undo_redo().add_undo_method(self, "undo_delete", id)
	var edit: Dictionary = host.finish_edit(ProjectSettings, "Delete assets", [{"check": can_undo.bind(id)}], false)
	host.edits.back().undo_result = undo_result.bind(id)
	job.edit_id = edit.edit_id
	job.undo_state = "available"

func undo_delete(id: String) -> void:
	var idle: Dictionary = _idle_error()
	undo_results[id] = idle if not idle.is_empty() else _restore(id)
	if undo_results[id].has("error"): push_warning("MCP asset undo refused: " + undo_results[id].error.message)

func undo_result(id: String) -> Dictionary:
	return undo_results.get(id, host.fail("UNDO_FAILED", "No asset restoration was started."))

func redo_delete(id: String) -> void:
	# Native redo is guarded by a preview taken after restoration settled.
	if not _idle_error().is_empty() or not redo_plans.has(id):
		push_warning("MCP asset redo unavailable; create a new deletion preview.")
		return
	var plan: Dictionary = redo_plans[id]
	var current: Dictionary = _plan(plan.options)
	if current.has("error") or current.get("fingerprint") != plan.fingerprint:
		push_warning("MCP asset redo refused because project state changed.")
		return
	var record: Dictionary = recovery.read_record(id)
	if record.has("error"): return
	if record.get("undo_invalidated", false): return
	# Reuse the durable record, but do not register a second native action during redo.
	var result: Dictionary = _delete(plan, record)
	if result.has("error"): push_warning(result.error.message)

func _finish(job: Dictionary) -> void:
	job.pending = []
	job.complete = job.failures.is_empty() and job.remaining.is_empty()
	job.status = "completed" if job.complete else ("partial" if not job.applied.is_empty() else "failed")
	if job.edit_id != null: job.undo_state = "available" if can_undo(job.deletion_id) else "unavailable"
	job.details_retained = host.operation_records.publish(job.operation_id, job)

func _settle(job: Dictionary) -> Dictionary:
	if job.applied.is_empty():
		_finish(job)
		return job
	job.editor_sync = "pending"
	job.undo_state = "unavailable"
	job.pending = ["editor_sync"]
	jobs[job.operation_id] = job
	EditorInterface.get_resource_filesystem().scan()
	job.details_retained = host.operation_records.publish(job.operation_id, job, true)
	_monitor.call_deferred(job.operation_id)
	return job.duplicate(true)

func _monitor(id: String) -> void:
	var fs := EditorInterface.get_resource_filesystem()
	await host.get_tree().process_frame
	var deadline: int = Time.get_ticks_msec() + 30000
	while not stopped and (fs.is_scanning() or fs.is_importing() or host.busy):
		if Time.get_ticks_msec() >= deadline:
			# A slow scan is still pending; retain its receipt and keep observing it.
			# Neither a request timeout nor result polling repeats filesystem writes.
			if jobs.has(id):
				jobs[id].note = "Waiting for the editor filesystem to settle."
				host.operation_records.publish(id, jobs[id], true)
				_monitor.call_deferred(id)
			return
		await host.get_tree().process_frame
	if stopped or not jobs.has(id): return
	var job: Dictionary = jobs[id]
	job.editor_sync = "completed"
	# Redo observes exactly the post-restore project, including unsaved source.
	if job.editor_sync == "completed" and job.has("deletion_id"):
		var record: Dictionary = recovery.read_record(job.deletion_id)
		if not record.has("error") and job.action == "delete_assets":
			job.recreated = []
			for entry: Dictionary in record.entries:
				if entry.uri not in job.applied: continue
				var exists: bool = FileAccess.file_exists(entry.uri) or DirAccess.dir_exists_absolute(entry.uri) or host.documents.store.states.has(entry.uri)
				if exists:
					job.recreated.append(entry.uri)
					if entry.uri not in job.remaining: job.remaining.append(entry.uri)
					_failure(job, "PATH_RECREATED", "The path was removed, then recreated while the editor was scanning.", entry.uri)
		if not record.has("error") and job.action == "restore_assets" and record.state == "restored" and not record.get("undo_invalidated", false):
			var options: Dictionary = {"paths": record.roots, "mode": "recoverable", "references": "allow_broken", "include_unsaved": []}
			for uri: String in host.documents.store.dirty_uris():
				if _inside(uri, record.roots): options.include_unsaved.append(uri)
			var plan: Dictionary = _plan(options)
			if not plan.has("error") and plan.blockers.is_empty():
				while redo_plans.size() >= 32: redo_plans.erase(redo_plans.keys()[0])
				redo_plans[record.deletion_id] = plan
	jobs.erase(id)
	_finish(job)

func _purge_preview(p: Dictionary) -> Dictionary:
	var ids: Array = p.get("deletion_ids", [])
	if ids.is_empty() or ids.size() > 200: return host.fail("INVALID_OPTIONS", "Provide one to 200 deletion IDs.")
	var signatures: Dictionary = {}
	var entries: Array = []
	for id: String in ids:
		if signatures.has(id): continue
		var record: Dictionary = recovery.read_record(id)
		if record.has("error"): return record
		var signature: Dictionary = recovery.signature(record)
		if signature.has("error"): return signature
		signatures[id] = signature
		entries.append(recovery.summary(record))
	return _store_plan("purge_deleted_assets", {"signatures": signatures, "entries": entries, "blockers": [], "coverage": {"scope": "Selected recovery records only; project assets and references are unchanged"}})

func _purge(plan: Dictionary) -> Dictionary:
	for id: String in plan.signatures:
		var record: Dictionary = recovery.read_record(id)
		if record.has("error") or recovery.signature(record) != plan.signatures[id]: return host.fail("STALE_PLAN", "A recovery record changed after preview; create a fresh purge plan.")
	var job: Dictionary = _new_job("purge_deleted_assets")
	if job.has("error"): return job
	plan.operation_id = job.operation_id
	job.deletion_ids = plan.signatures.keys()
	job.purged_entries = []
	job.retained_entries = []
	for id: String in plan.signatures:
		var record: Dictionary = recovery.read_record(id)
		if record.has("error"):
			job.remaining.append(id)
			_failure(job, "RECOVERY_RECORD_FAILED", record.error.message, id)
			continue
		var failed: bool = false
		record.state = "purging"
		record.undo_invalidated = true
		if recovery.save(record) != OK:
			job.remaining.append(id)
			_failure(job, "RECOVERY_RECORD_FAILED", "Cannot invalidate Undo before purging recovery data.", id)
			continue
		for entry: Dictionary in record.entries:
			if entry.kind != "file": continue
			var path: String = recovery.blob(id, entry.uri)
			if not FileAccess.file_exists(path): continue
			var error: Error = DirAccess.remove_absolute(path) if host.paths_safe(path) else ERR_INVALID_PARAMETER
			if error == OK: job.purged_entries.append({"deletion_id": id, "uri": entry.uri})
			else:
				failed = true
				job.retained_entries.append({"deletion_id": id, "uri": entry.uri})
				_failure(job, "PURGE_FAILED", error_string(error), entry.uri)
		if not failed:
			var path: String = recovery.directory(id)
			# The manifest (including unsaved source) is the last recovery copy removed.
			if DirAccess.dir_exists_absolute(path.path_join("files")) and DirAccess.remove_absolute(path.path_join("files")) != OK:
				failed = true
				job.retained_entries.append({"deletion_id": id, "uri": path.path_join("files")})
			var temp: String = path.path_join("manifest.json.tmp")
			if FileAccess.file_exists(temp) and DirAccess.remove_absolute(temp) != OK: failed = true
			if not failed and DirAccess.remove_absolute(path.path_join("manifest.json")) != OK: failed = true
			if not failed: DirAccess.remove_absolute(path)
		if failed:
			job.remaining.append(id)
			_failure(job, "PURGE_INCOMPLETE", "Some recovery data remains; inspect retained entries before retrying.", id)
		else:
			job.applied.append(id)
		identities.erase(id)
		redo_plans.erase(id)
	_finish(job)
	return job
