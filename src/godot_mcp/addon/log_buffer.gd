@tool
extends Logger
## Logger callbacks may run on worker threads. Never call the engine logger here.
var mutex := Mutex.new()
var entries: Array[Dictionary] = []
var serial: int = 0
var dropped: int = 0

func _append(kind: String, message: String, uri: String = "", line: int = 0) -> void:
	mutex.lock()
	serial += 1
	var entry := {"cursor": serial, "kind": kind, "message": message, "uri": uri, "line": line, "time_usec": Time.get_ticks_usec(), "count": 1}
	if not entries.is_empty() and entries.back().message == message and entries.back().uri == uri and entries.back().kind == kind:
		entries.back().count += 1
		entries.back().cursor = serial
		entries.back().time_usec = entry.time_usec
	else:
		entries.append(entry)
		if entries.size() > 2000:
			entries.pop_front()
			dropped += 1
	mutex.unlock()

func _log_message(message: String, error: bool) -> void:
	_append("error" if error else "log", message)

func _log_error(_function: String, file: String, line: int, code: String, rationale: String, _editor_notify: bool, error_type: int, _script_backtraces: Array[ScriptBacktrace]) -> void:
	_append("warning" if error_type == ERROR_TYPE_WARNING else "error", rationale if not rationale.is_empty() else code, file, line)

func read(since: int = 0, limit: int = 1000) -> Dictionary:
	mutex.lock()
	var result: Array[Dictionary] = []
	for entry: Dictionary in entries:
		if entry.cursor > since:
			result.append(entry.duplicate(true))
			if result.size() >= limit:
				break
	var cursor: int = result.back().cursor if not result.is_empty() else serial
	var value := {"entries": result, "cursor": cursor, "dropped": dropped, "has_more": cursor < serial}
	mutex.unlock()
	return value
