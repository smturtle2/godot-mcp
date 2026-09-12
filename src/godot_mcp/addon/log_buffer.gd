@tool
extends Logger
## Logger callbacks may run on worker threads. Never call the engine logger here.
var mutex := Mutex.new()
var entries: Array[Dictionary] = []
var serial: int = 0
var dropped: int = 0
var journal_path: String = ""

func start_journal() -> bool:
	journal_path = "res://.godot-mcp/runtime-logs/%d.jsonl" % OS.get_process_id()
	DirAccess.make_dir_recursive_absolute(journal_path.get_base_dir())
	var file := FileAccess.open(journal_path, FileAccess.WRITE)
	if not file:
		journal_path = ""
		return false
	file.close()
	return true

static func read_journal(pid: int, since: int, limit: int, kinds: Array) -> Dictionary:
	var file := FileAccess.open("res://.godot-mcp/runtime-logs/%d.jsonl" % pid, FileAccess.READ)
	if not file: return {"entries": [], "cursor": since, "has_more": false, "collection_state": "unavailable"}
	var buffer = load("res://addons/godot_mcp/log_buffer.gd").new()
	var complete: bool = true
	while file.get_position() < file.get_length():
		var entry: Variant = JSON.parse_string(file.get_line())
		if not entry is Dictionary or not entry.has("cursor"):
			complete = false
			break
		buffer.serial = int(entry.cursor)
		if not buffer.entries.is_empty() and buffer.entries.back().message == entry.message and buffer.entries.back().uri == entry.uri and buffer.entries.back().kind == entry.kind:
			buffer.entries[-1] = entry
		else:
			buffer.entries.append(entry)
	buffer.dropped = maxi(0, int(buffer.entries[0].cursor) - 1) if not buffer.entries.is_empty() else 0
	var result: Dictionary = buffer.read(since, limit, kinds)
	result.collection_state = "available" if complete else "partial"
	return result

func mark() -> int:
	mutex.lock()
	var cursor: int = serial
	mutex.unlock()
	return cursor

func _append(kind: String, message: String, uri: String = "", line: int = 0, details: Dictionary = {}) -> void:
	mutex.lock()
	serial += 1
	var entry := {"cursor": serial, "kind": kind, "message": message.left(8192), "uri": uri, "line": line, "time_usec": Time.get_ticks_usec(), "count": 1}
	entry.merge(details)
	if not entries.is_empty() and entries.back().message == message and entries.back().uri == uri and entries.back().kind == kind:
		entries.back().count += 1
		entries.back().cursor = serial
		entries.back().time_usec = entry.time_usec
	else:
		entries.append(entry)
		if entries.size() > 2000:
			entries.pop_front()
			dropped += 1
	if not journal_path.is_empty():
		var file := FileAccess.open(journal_path, FileAccess.READ_WRITE)
		if file:
			if file.get_length() > 2 * 1024 * 1024:
				file.close()
				file = FileAccess.open(journal_path, FileAccess.WRITE)
				if file:
					for retained: Dictionary in entries.slice(-64): file.store_line(JSON.stringify(retained))
			else:
				file.seek_end()
				file.store_line(JSON.stringify(entries.back()))
			if file:
				file.flush()
				file.close()
	mutex.unlock()

func _log_message(message: String, error: bool) -> void:
	_append("error" if error else "log", message)

func _log_error(function: String, file: String, line: int, code: String, rationale: String, _editor_notify: bool, error_type: int, script_backtraces: Array[ScriptBacktrace]) -> void:
	var traces: Array = []
	for trace: ScriptBacktrace in script_backtraces:
		if traces.size() >= 4: break
		traces.append(str(trace).left(4000))
	_append("warning" if error_type == ERROR_TYPE_WARNING else "error", rationale if not rationale.is_empty() else code, file, line, {"function": function, "code": code, "backtraces": traces})

static func kind_matches(entry: Dictionary, kinds: Array) -> bool:
	return kinds.is_empty() or entry.get("kind", "") in kinds

static func filter_entries(source: Array, kinds: Array) -> Array:
	if kinds.is_empty(): return source.duplicate(true)
	return source.filter(func(entry: Dictionary) -> bool: return kind_matches(entry, kinds))

func read(since: int = 0, limit: int = 1000, kinds: Array = []) -> Dictionary:
	mutex.lock()
	var result: Array[Dictionary] = []
	var cursor: int = serial
	var scanned: bool = false
	for entry: Dictionary in entries:
		if entry.cursor <= since: continue
		scanned = true
		cursor = entry.cursor
		if kind_matches(entry, kinds):
			result.append(entry.duplicate(true))
			if result.size() >= limit: break
	var has_more := false
	if scanned and result.size() >= limit:
		for entry: Dictionary in entries:
			if entry.cursor > cursor and kind_matches(entry, kinds):
				has_more = true
				break
	var value := {"entries": result, "cursor": cursor, "dropped": dropped, "has_more": has_more}
	mutex.unlock()
	return value
