@tool
extends RefCounted
## Current diagnostic requests own their lifecycle; the validator owns compiler
## serialization and cache reuse, and operation records remain inert snapshots.
var host: EditorPlugin
var jobs: Dictionary = {}
var stopped: bool = false
const LogBuffer = preload("res://addons/godot_mcp/log_buffer.gd")

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func shutdown() -> void:
	stopped = true
	jobs.clear()

func pending() -> Array:
	var result: Array = []
	for id: String in jobs: result.append({"operation_id": id, "tool": "get_diagnostics", "phase": "validation"})
	return result

func start(p: Dictionary) -> Dictionary:
	if jobs.size() >= 16: return host.fail("OPERATION_LIMIT", "Wait for a pending diagnostic result before starting another request.")
	var reserved: Dictionary = host.operation_records.begin("get_diagnostics")
	if reserved.has("error"): return reserved
	var id: String = reserved.operation_id
	var result: Dictionary = {"operation_id": id, "status": "pending", "current": true, "sources": [], "state": "pending", "scope": "requested_sources" if not p.get("uris", []).is_empty() else "project_sources", "coverage": {"complete": false, "reason": "Validation is pending."}}
	jobs[id] = p.duplicate(true)
	result.details_retained = host.operation_records.publish(id, result, true)
	_advance.call_deferred(id)
	return result

func _advance(id: String) -> void:
	if stopped or not jobs.has(id): return
	var result: Dictionary = await _evaluate(jobs[id])
	if stopped: return
	result.operation_id = id
	result.status = "completed"
	result.details_retained = host.operation_records.publish(id, result, false)
	jobs.erase(id)

func _evaluate(p: Dictionary) -> Dictionary:
	var uris: Array = p.get("uris", []).duplicate()
	var coverage: Dictionary = {"complete": true, "skipped_files": []}
	var scope: String = "requested_sources"
	if uris.is_empty():
		coverage = host.documents.search.source_uris()
		if coverage.has("error"): return coverage
		uris = coverage.uris
		scope = "project_sources"
	if uris.size() > 200:
		coverage.complete = false
		coverage.skipped_files.append_array(uris.slice(200))
		uris = uris.slice(0, 200)
	if uris.is_empty(): return {"sources": [], "current": true, "state": "unavailable", "scope": scope, "coverage": coverage, "reason": "No authored sources are available to validate."}
	var checked: Dictionary = await host.documents.validate_sources(uris)
	if checked.has("error"): return checked
	var state: String = "valid"
	var errors: int = 0
	var warnings: int = 0
	var fresh: bool = true
	for source: Dictionary in checked.sources:
		if source.state not in ["valid", "invalid"]: fresh = false
		if source.state == "invalid": state = "invalid"
		elif source.state in ["pending", "unavailable"] and state != "invalid": state = source.state
		for entry: Dictionary in source.entries:
			if entry.get("kind") == "error": errors += 1
			elif entry.get("kind") == "warning": warnings += 1
		if p.has("kinds"): source.entries = LogBuffer.filter_entries(source.entries, p.kinds)
	if not coverage.complete and state == "valid": state = "unavailable"
	var result: Dictionary = {"sources": checked.sources, "current": true, "state": state, "scope": scope, "coverage": coverage, "observed_errors": errors, "observed_warnings": warnings}
	if fresh and coverage.complete:
		result.error_count = errors
		result.warning_count = warnings
	for key: String in ["snapshot_id", "cache", "fingerprint"]:
		if checked.has(key): result[key] = checked[key]
	return result
