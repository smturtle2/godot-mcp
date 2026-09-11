extends RefCounted
## Bounded, inert result snapshots. Domain modules own execution and recovery.
var host: Object
var max_records: int = 64
var max_bytes: int = 16 * 1024 * 1024
var records: Dictionary = {}
var sequence: int = 0
var retained_bytes: int = 0

func _init(editor_host: Object) -> void:
	host = editor_host

func _erase(id: String) -> void:
	retained_bytes -= int(records[id].bytes)
	records.erase(id)

func _evict_completed(except_id: String = "") -> bool:
	for id: String in records:
		if id != except_id and not records[id].pending:
			_erase(id)
			return true
	return false

func begin(tool: String) -> Dictionary:
	while records.size() >= max_records:
		if not _evict_completed(): return host.fail("OPERATION_LIMIT", "All retained operation slots are pending; wait for completion before starting another operation.")
	sequence += 1
	var id: String = "operation-" + host.epoch + "-" + str(sequence)
	records[id] = {"tool": tool, "pending": true, "recorded_at_usec": Time.get_ticks_usec(), "json": "", "bytes": 0}
	return {"operation_id": id}

func discard(id: String) -> void:
	if records.has(id): _erase(id)

func publish(id: String, result: Dictionary, pending: bool = false) -> bool:
	if not records.has(id): return false
	var entry: Dictionary = records[id]
	retained_bytes -= int(entry.bytes)
	entry.json = JSON.stringify(result)
	entry.bytes = entry.json.to_utf8_buffer().size()
	entry.pending = pending
	entry.recorded_at_usec = Time.get_ticks_usec()
	retained_bytes += int(entry.bytes)
	while retained_bytes > max_bytes and _evict_completed(id): pass
	if retained_bytes > max_bytes:
		# Preserve the identity of pending work, never its execution state. A later
		# publication can become available again. Completed oversized records expire.
		retained_bytes -= int(entry.bytes)
		entry.json = ""
		entry.bytes = 0
		if not pending: records.erase(id)
		return false
	return true

func get_result(id: String) -> Dictionary:
	if not records.has(id):
		var prefix: String = "operation-" + host.epoch + "-"
		var suffix: String = id.trim_prefix(prefix)
		var expired: bool = id.begins_with(prefix) and suffix.is_valid_int() and int(suffix) > 0 and int(suffix) <= sequence
		return host.fail("OPERATION_RESULT_EXPIRED" if expired else "OPERATION_NOT_FOUND", "Operation results are bounded to the current editor session; this result is no longer retained." if expired else "This operation ID does not exist in the current editor session.", {"operation_id": id, "editor_epoch": host.epoch})
	var entry: Dictionary = records[id]
	if entry.json.is_empty():
		return host.fail("OPERATION_RESULT_UNAVAILABLE", "The operation is pending and has no retained result within the byte limit yet.", {"operation_id": id, "pending": entry.pending})
	var result: Dictionary = JSON.parse_string(entry.json)
	var edit_id: Variant = result.get("undo", {}).get("edit_id", result.get("edit_id"))
	return {"operation_id": id, "tool": entry.tool, "editor_epoch": host.epoch,
		"recorded_at_usec": entry.recorded_at_usec, "snapshot": true, "pending": entry.pending,
		"result": result, "current_undo": host.undo_availability(edit_id)}
