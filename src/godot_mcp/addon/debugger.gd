@tool
extends EditorDebuggerPlugin
var host: EditorPlugin
var active_session: int = -1
var pending: Dictionary = {}
var serial: int = 0
var pause_serial: int = 0
var pause_id: String = ""

func _has_capture(prefix: String) -> bool:
	return prefix == "godot_mcp"

func _capture(message: String, data: Array, session_id: int) -> bool:
	if message == "godot_mcp:ready" and not data.is_empty():
		if host.runtime.on_ready(data[0]): active_session = session_id
		return true
	if message == "godot_mcp:result" and data.size() == 2:
		if session_id == active_session and pending.has(int(data[0])):
			pending[int(data[0])] = data[1]
		return true
	return false

func _setup_session(session_id: int) -> void:
	var session := get_session(session_id)
	session.stopped.connect(_stopped.bind(session_id))
	session.breaked.connect(_breaked.bind(session_id))
	session.continued.connect(_continued.bind(session_id))

func _stopped(session_id: int) -> void:
	if active_session == session_id:
		host.runtime.ready = false
		active_session = -1
		pause_id = ""
		for key: Variant in pending: pending[key] = host.fail("GAME_STOPPED", "The game stopped during this request.")

func _breaked(_can_debug: bool, session_id: int) -> void:
	if session_id == active_session or active_session < 0:
		pause_serial += 1
		pause_id = "pause-" + host.epoch + "-" + str(pause_serial)

func _continued(session_id: int) -> void:
	if session_id == active_session: pause_id = ""

func state() -> Dictionary:
	var session: EditorDebuggerSession = get_session(active_session) if active_session >= 0 else null
	return {"active": session != null and session.is_active(), "paused": session != null and session.is_breaked(), "debuggable": session != null and session.is_debuggable(), "pause_id": pause_id, "run_id": host.runtime.run_id if host.runtime else "", "session_id": active_session}

func request(method: String, params: Dictionary) -> Dictionary:
	if active_session < 0 or not host.runtime.ready: return host.fail("RUNTIME_DISCONNECTED", "Runtime helper is not connected.")
	var session := get_session(active_session)
	if session.is_breaked(): return host.fail("DEBUGGER_PAUSED", "Resume the debugger before runtime observation/input.")
	serial += 1
	var id: int = serial
	pending[id] = null
	session.send_message("godot_mcp:request", [id, method, params])
	var event_ms: int = 0
	for event: Dictionary in params.get("events", []): event_ms = maxi(event_ms, int(event.get("at_ms", 0)))
	var timeout: int = maxi(30000, int(params.get("timeout_ms", 0)) + int(params.get("duration_ms", 0)) + event_ms + 5000)
	var deadline: int = Time.get_ticks_msec() + timeout
	while pending.has(id) and pending[id] == null and Time.get_ticks_msec() < deadline:
		if session.is_breaked():
			pending.erase(id)
			return host.fail("DEBUGGER_PAUSED", "The request was delivered, but execution hit a breakpoint before completion. Inspect the debugger; do not blindly retry input.", {"request_delivered": true})
		await host.get_tree().process_frame
	var result: Variant = pending.get(id)
	pending.erase(id)
	if not result is Dictionary: return host.fail("RUNTIME_TIMEOUT", "Game did not respond before the deadline.")
	return result
