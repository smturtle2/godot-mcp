extends Node
## Inert without an attached editor debugger. No network listener in game builds.
const CaptureImage = preload("res://addons/godot_mcp/capture_image.gd")
const Codec = preload("res://addons/godot_mcp/codec.gd")
const LogBuffer = preload("res://addons/godot_mcp/log_buffer.gd")
const OperationResult = preload("res://addons/godot_mcp/operation_result.gd")
const SourceManifest = preload("res://addons/godot_mcp/source_manifest.gd")
var held: Dictionary = {}
var held_mouse_buttons: int = 0
var captures: Dictionary = {}
var logs: Logger
var busy: bool = false
var active: bool = false

func _ready() -> void:
	if not EngineDebugger.is_active():
		set_process(false)
		return
	process_mode = Node.PROCESS_MODE_ALWAYS
	active = true
	logs = LogBuffer.new()
	OS.add_logger(logs)
	EngineDebugger.register_message_capture("godot_mcp", _capture)
	EngineDebugger.send_message("godot_mcp:ready", [{"pid": OS.get_process_id(), "renderer": RenderingServer.get_current_rendering_method(), "display": DisplayServer.get_name(), "source_startup": SourceManifest.startup()}])

func _exit_tree() -> void:
	if active:
		release_input()
		EngineDebugger.unregister_message_capture("godot_mcp")
		OS.remove_logger(logs)

func _capture(message: String, data: Array) -> bool:
	if message != "request" or data.size() != 3: return false
	_handle(int(data[0]), str(data[1]), data[2])
	return true

func _handle(id: int, method: String, p: Dictionary) -> void:
	if busy:
		EngineDebugger.send_message("godot_mcp:result", [id, fail("RUNTIME_BUSY", "A runtime request is already running.")])
		return
	busy = true
	var result: Dictionary = await dispatch(method, p)
	result.observed_at_usec = Time.get_ticks_usec()
	result.frame = Engine.get_process_frames()
	EngineDebugger.send_message("godot_mcp:result", [id, result])
	busy = false

func fail(code: String, message: String) -> Dictionary:
	return {"error": {"code": code, "message": message}}

func node_at(ref: Dictionary) -> Node:
	var path: String = ref.get("path", "/root")
	if not path.begins_with("/root") or ".." in path.split("/"): return null
	return get_node_or_null(NodePath(path))

func property_exists(object: Object, property: String) -> bool:
	for prop: Dictionary in object.get_property_list():
		if str(prop.name) == property: return true
	return false

func select_case(value: Variant, names: Array[String], field: String) -> Dictionary:
	if not value is Dictionary or value.size() != 1:
		return fail("INVALID_" + field.to_upper(), field + " must select exactly one named kind.")
	var kind: String = str(value.keys()[0])
	if kind not in names or not value[kind] is Dictionary:
		return fail("INVALID_" + field.to_upper(), field + " contains an unsupported or non-object kind.")
	return {"kind": kind, "value": value[kind]}

func dispatch(method: String, p: Dictionary) -> Dictionary:
	match method:
		"inspect_runtime":
			var node := node_at(p.get("node", {}))
			if not node: return fail("NODE_NOT_FOUND", "Runtime node does not exist.")
			return {"node": describe(node, p.get("properties", []), int(p.get("depth", 0))), "scene": get_tree().current_scene.scene_file_path if get_tree().current_scene else null}
		"capture_viewport": return await capture(p)
		"send_input": return await send_input(p)
		"wait_for_condition": return await wait_condition(p.condition, int(p.get("timeout_ms", 5000)), int(p.get("poll_ms", 16)))
		"sample_performance": return await sample_performance(p)
		"release_input":
			release_input()
			return {"released": true}
		"get_diagnostics": return logs.read(int(p.get("since", 0)), int(p.get("limit", 200)), p.get("kinds", []))
		"_source_state": return source_state()
	return fail("UNKNOWN_TOOL", method)

func source_state() -> Dictionary:
	var scripts: Dictionary = {}
	var scenes: Array = []
	var pending: Array[Node] = [get_tree().root]
	var count: int = 0
	while not pending.is_empty() and count < 10000:
		var node: Node = pending.pop_back()
		count += 1
		for child: Node in node.get_children(): pending.append(child)
		if not node.scene_file_path.is_empty() and node.scene_file_path not in scenes: scenes.append(node.scene_file_path)
		var script: Script = node.get_script() as Script
		while script:
			if not script.resource_path.is_empty(): scripts[script.resource_path] = script.source_code.sha256_text()
			script = script.get_base_script()
	return {"scripts": scripts, "scenes": scenes, "complete": pending.is_empty(), "scope": "currently instantiated nodes and their script ancestry; dynamic resource loads are not exhaustive"}

func describe(node: Node, properties: Array, depth: int) -> Dictionary:
	var values: Dictionary = {}
	var names: Array = properties
	if names.is_empty():
		names = ["position", "rotation", "visible", "process_mode"]
	for property: String in names:
		if property_exists(node, property): values[property] = Codec.encode(node.get(property))
	var result: Dictionary = {"path": str(node.get_path()), "class": node.get_class(), "properties": values, "children": []}
	if depth > 0:
		var count: int = 0
		for child: Node in node.get_children():
			if count >= 500:
				result.truncated = true
				break
			result.children.append(describe(child, properties, depth - 1))
			count += 1
	return result

func capture(p: Dictionary) -> Dictionary:
	if DisplayServer.get_name() == "headless": return fail("RENDERER_UNAVAILABLE", "Game capture requires an actual rendering display.")
	if p.get("framing", "current") != "current" or p.has("bounds_2d") or p.has("bounds_3d"): return fail("INVALID_FRAMING", "Game capture preserves the running game's view; use an editor viewport to frame content.")
	await RenderingServer.frame_post_draw
	var uri: String = "godot://captures/" + str(OS.get_process_id()) + "/" + str(Time.get_ticks_usec()) + ".png"
	var result: Dictionary = CaptureImage.pack(get_viewport().get_texture().get_image(), p, {"uri": uri, "kind": "game", "scene": get_tree().current_scene.scene_file_path if get_tree().current_scene else "", "captured_at": Time.get_datetime_string_from_system(true), "observed_at_usec": Time.get_ticks_usec(), "frame": Engine.get_process_frames(), "input_supported": true, "coordinate_space": "capture pixels; pass capture_uri to send_input"}, get_viewport().get_visible_rect().size)
	if result.has("error"): return result
	captures[uri] = {"rect": Codec.decode(result.crop), "size": Vector2i(result.width, result.height), "original": Codec.decode(result.pixel_size), "viewport": get_viewport().get_visible_rect().size}
	if captures.size() > 32: captures.erase(captures.keys()[0])
	return result

func release_input() -> void:
	for event: InputEvent in held.values():
		if event is InputEventKey or event is InputEventMouseButton or event is InputEventScreenTouch or event is InputEventAction:
			if event is InputEventMouseButton:
				held_mouse_buttons &= ~mouse_button_bit(event.button_index)
				event.button_mask = held_mouse_buttons
				event.pressed = false
			Input.parse_input_event(event)
	held.clear()
	held_mouse_buttons = 0

func event_key(spec: Dictionary) -> String:
	var kind: String = str(spec.get("kind", ""))
	var payload: Dictionary = spec.get("payload", {})
	return kind + ":" + str(payload.get("key", payload.get("button", payload.get("action", payload.get("index", 0)))))

func mouse_button_bit(button: int) -> int:
	if button < MOUSE_BUTTON_LEFT or button > MOUSE_BUTTON_MIDDLE: return 0
	return 1 << (button - MOUSE_BUTTON_LEFT)

func capture_position(position: Vector2, info: Dictionary) -> Vector2:
	return (Vector2(info.rect.position) + position * Vector2(info.rect.size) / Vector2(info.size)) * Vector2(info.viewport) / Vector2(info.original)

func capture_delta(delta: Vector2, info: Dictionary) -> Vector2:
	return delta * Vector2(info.rect.size) / Vector2(info.size) * Vector2(info.viewport) / Vector2(info.original)

func make_event(spec: Dictionary, capture_uri: String) -> Dictionary:
	var selected: Dictionary = select_case(spec.get("event", {}), ["key", "mouse_button", "mouse_motion", "touch", "drag", "action"], "event")
	if selected.has("error"): return selected
	var kind: String = selected.kind
	var data: Dictionary = selected.value
	var position := Codec.v2(data.get("position", {}))
	if not capture_uri.is_empty() and data.has("position"):
		if not captures.has(capture_uri): return fail("STALE_CAPTURE", "Capture metadata expired or belongs to another run.")
		var info: Dictionary = captures[capture_uri]
		position = capture_position(position, info)
	var event: InputEvent
	match kind:
		"key":
			var code: int = OS.find_keycode_from_string(str(data.get("key", "")))
			if code == KEY_NONE: return fail("INVALID_KEY", "Unknown key name.")
			var key := InputEventKey.new()
			key.keycode = code
			if data.get("physical", false): key.physical_keycode = code
			key.pressed = data.get("pressed", false)
			event = key
		"mouse_button":
			var buttons := {"left": MOUSE_BUTTON_LEFT, "right": MOUSE_BUTTON_RIGHT, "middle": MOUSE_BUTTON_MIDDLE, "wheel_up": MOUSE_BUTTON_WHEEL_UP, "wheel_down": MOUSE_BUTTON_WHEEL_DOWN}
			if not buttons.has(data.get("button", "")): return fail("INVALID_BUTTON", "Unknown mouse button.")
			var mouse := InputEventMouseButton.new()
			mouse.button_index = buttons[data.button]
			mouse.position = position
			mouse.global_position = position
			mouse.pressed = data.get("pressed", false)
			event = mouse
		"mouse_motion":
			var mouse := InputEventMouseMotion.new()
			mouse.position = position
			mouse.global_position = position
			mouse.relative = Codec.v2(data.get("relative", {}))
			if not capture_uri.is_empty(): mouse.relative = capture_delta(mouse.relative, captures[capture_uri])
			event = mouse
		"touch":
			var touch := InputEventScreenTouch.new()
			touch.index = int(data.get("index", 0))
			touch.position = position
			touch.pressed = data.get("pressed", false)
			event = touch
		"drag":
			var touch := InputEventScreenDrag.new()
			touch.index = int(data.get("index", 0))
			touch.position = position
			touch.relative = Codec.v2(data.get("relative", {}))
			if not capture_uri.is_empty(): touch.relative = capture_delta(touch.relative, captures[capture_uri])
			event = touch
		"action":
			if not InputMap.has_action(data.get("action", "")): return fail("ACTION_NOT_FOUND", "The input action is not defined.")
			var action := InputEventAction.new()
			action.action = str(data.action)
			action.pressed = data.get("pressed", false)
			action.strength = float(data.get("strength", 1))
			event = action
		_: return fail("INVALID_EVENT", "Unsupported input event type.")
	if event is InputEventWithModifiers:
		event.shift_pressed = data.get("shift", false)
		event.ctrl_pressed = data.get("ctrl", false)
		event.alt_pressed = data.get("alt", false)
		event.meta_pressed = data.get("meta", false)
	return {"event": event, "kind": kind, "payload": data}

func signal_seen(watch: Dictionary) -> void:
	if not watch.seen:
		watch.satisfied_at_usec = Time.get_ticks_usec()
		watch.satisfied_frame = Engine.get_process_frames()
	watch.seen = true

func watch_condition(condition: Dictionary) -> Dictionary:
	if condition.is_empty(): return {}
	var selected: Dictionary = select_case(condition, ["scene", "node", "property", "signal"], "condition")
	if selected.has("error"): return selected
	var kind: String = selected.kind
	if kind != "signal": return {}
	var data: Dictionary = selected.value
	var node := node_at(data.get("node", {}))
	var name: String = data.get("signal", "")
	if not node or not node.has_signal(name): return fail("SIGNAL_NOT_FOUND", "Signal condition target does not exist.")
	var count: int = 0
	for signal_info: Dictionary in node.get_signal_list():
		if str(signal_info.name) == name: count = signal_info.args.size()
	var watch: Dictionary = {"node": node, "signal": name, "seen": false}
	var callback: Callable = signal_seen.bind(watch).unbind(count)
	watch.callback = callback
	node.connect(name, callback)
	return watch

func unwatch(watch: Dictionary) -> void:
	if watch.has("node") and is_instance_valid(watch.node) and watch.node.is_connected(watch.signal, watch.callback):
		watch.node.disconnect(watch.signal, watch.callback)

func observation(condition: Dictionary, watch: Dictionary) -> Dictionary:
	var result: Dictionary = _condition_value(condition, watch)
	result.observed_at_usec = Time.get_ticks_usec()
	result.frame = Engine.get_process_frames()
	if result.get("satisfied", false):
		result.satisfied_at_usec = watch.get("satisfied_at_usec", result.observed_at_usec)
		result.satisfied_frame = watch.get("satisfied_frame", result.frame)
	return result

func _condition_value(condition: Dictionary, watch: Dictionary) -> Dictionary:
	var selected: Dictionary = select_case(condition, ["scene", "node", "property", "signal"], "condition")
	if selected.has("error"): return selected
	var kind: String = selected.kind
	var data: Dictionary = selected.value
	if kind == "scene":
		var current: String = get_tree().current_scene.scene_file_path if get_tree().current_scene else ""
		return {"satisfied": current == data.get("uri", ""), "value": current}
	if kind == "signal": return {"satisfied": watch.get("seen", false), "value": watch.get("seen", false)}
	var node := node_at(data.get("node", {}))
	if kind == "node": return {"satisfied": (node != null) == bool(data.get("exists", true)), "value": node != null}
	if not node: return {"satisfied": false, "value": null, "reason": "node_missing"}
	if kind != "property": return fail("INVALID_CONDITION", "Unsupported condition kind.")
	var property: String = data.get("property", "")
	if not property_exists(node, property): return fail("PROPERTY_NOT_FOUND", "Condition property does not exist.")
	var actual: Variant = node.get(property)
	var expected: Variant = Codec.decode(data.get("value"))
	var operator: String = data.get("operator", "eq")
	var yes: bool = false
	if operator in ["gt", "gte", "lt", "lte"] and not ((actual is float or actual is int) and (expected is float or expected is int)):
		return fail("INVALID_COMPARISON", "Ordering comparisons require numbers.")
	match operator:
		"eq": yes = actual == expected if typeof(actual) == typeof(expected) or ((actual is int or actual is float) and (expected is int or expected is float)) else false
		"ne": yes = actual != expected if typeof(actual) == typeof(expected) or ((actual is int or actual is float) and (expected is int or expected is float)) else true
		"gt": yes = actual > expected
		"gte": yes = actual >= expected
		"lt": yes = actual < expected
		"lte": yes = actual <= expected
	return {"satisfied": yes, "value": Codec.encode(actual)}

func wait_condition(condition: Dictionary, timeout: int, poll: int, existing_watch: Dictionary = {}) -> Dictionary:
	var watch: Dictionary = existing_watch if not existing_watch.is_empty() else watch_condition(condition)
	if watch.has("error"): return watch
	var start: int = Time.get_ticks_msec()
	var last: Dictionary = observation(condition, watch)
	while not last.has("error") and not last.get("satisfied", false) and Time.get_ticks_msec() - start < timeout:
		await get_tree().create_timer(minf(float(poll) / 1000, float(timeout - (Time.get_ticks_msec() - start)) / 1000), true).timeout
		last = observation(condition, watch)
	unwatch(watch)
	last.elapsed_ms = Time.get_ticks_msec() - start
	last.timed_out = not last.has("error") and not last.get("satisfied", false)
	return last

func observe_properties(selections: Array) -> Array:
	var observations: Array = []
	for selection: Dictionary in selections:
		var node := node_at(selection.node)
		var values: Dictionary = {}
		var missing: Array = []
		for property: String in selection.properties:
			if is_instance_valid(node) and property_exists(node, property): values[property] = Codec.encode(node.get(property))
			else: missing.append(property)
		observations.append({"node": selection.node, "exists": is_instance_valid(node), "properties": values, "unavailable_properties": missing, "observed_at_usec": Time.get_ticks_usec(), "frame": Engine.get_process_frames()})
	return observations

func send_input(p: Dictionary) -> Dictionary:
	var events: Array[Dictionary] = []
	var previous: int = -1
	for spec: Dictionary in p.get("events", []):
		var time: int = int(spec.get("at_ms", 0))
		if time < previous: return fail("INVALID_SEQUENCE", "Event at_ms values must be nondecreasing.")
		previous = time
		var made: Dictionary = make_event(spec, str(p.get("capture_uri", "")))
		if made.has("error"): return made
		events.append({"at_ms": time, "event": made.event, "kind": made.kind, "payload": made.payload})
	var watch: Dictionary = watch_condition(p.get("wait_for", {}))
	if watch.has("error"): return watch
	var observations: Dictionary = {}
	if p.has("observe"): observations.before = observe_properties(p.observe)
	var injections: Array = []
	var start: int = Time.get_ticks_msec()
	for item: Dictionary in events:
		while Time.get_ticks_msec() - start < item.at_ms: await get_tree().process_frame
		if item.event is InputEventMouseButton:
			var bit: int = mouse_button_bit(item.event.button_index)
			if bit != 0:
				if item.event.pressed: held_mouse_buttons |= bit
				else: held_mouse_buttons &= ~bit
			item.event.button_mask = held_mouse_buttons
		elif item.event is InputEventMouseMotion:
			item.event.button_mask = held_mouse_buttons
		injections.append({"index": injections.size(), "at_ms": item.at_ms, "injected_at_usec": Time.get_ticks_usec(), "frame": Engine.get_process_frames()})
		Input.parse_input_event(item.event)
		if item.payload.has("pressed"):
			var key: String = event_key(item)
			if item.event is InputEventMouseButton and mouse_button_bit(item.event.button_index) == 0:
				pass
			elif item.payload.pressed: held[key] = item.event.duplicate()
			else: held.erase(key)
	# Due events share an injection frame. Yield once after the batch; this is
	# not a claim that every gameplay reaction has finished processing.
	await get_tree().process_frame
	var result: Dictionary = {"processed": events.size(), "elapsed_ms": Time.get_ticks_msec() - start, "injections": injections}
	if p.get("release_after", false):
		result.release = {"injected_at_usec": Time.get_ticks_usec(), "frame": Engine.get_process_frames(), "count": held.size()}
		release_input()
	result.held_inputs = held.size()
	var failures: Array = []
	if p.has("wait_for"):
		result.condition = await wait_condition(p.wait_for, int(p.get("timeout_ms", 5000)), 16, watch)
		if result.condition.has("error"):
			failures.append(OperationResult.failure("condition", result.condition.error))
		elif not result.condition.get("satisfied", false):
			failures.append(OperationResult.failure("condition", {"code": "CONDITION_TIMEOUT", "message": "Input was sent, but the requested condition was not satisfied before the timeout."}))
	else: unwatch(watch)
	if p.has("observe"):
		observations.after = observe_properties(p.observe)
		result.observations = observations
	if p.get("capture_after", false):
		result.capture = await capture({})
		if result.capture.has("error"): failures.append(OperationResult.failure("capture", result.capture.error))
	if not failures.is_empty(): result.recovery = "Input events remain applied. Retry only the failed observation or capture; do not resend the input sequence automatically."
	return OperationResult.finish(result, not events.is_empty(), failures)

func sample_performance(p: Dictionary) -> Dictionary:
	var metrics: Dictionary = {"process_ms": [Performance.TIME_PROCESS, 1000.0, "ms"], "physics_ms": [Performance.TIME_PHYSICS_PROCESS, 1000.0, "ms"], "fps": [Performance.TIME_FPS, 1.0, "frames/s"], "memory_bytes": [Performance.MEMORY_STATIC, 1.0, "bytes"], "objects": [Performance.OBJECT_COUNT, 1.0, "count"], "draw_calls": [Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME, 1.0, "calls/frame"], "primitives": [Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME, 1.0, "primitives/frame"], "video_memory_bytes": [Performance.RENDER_VIDEO_MEM_USED, 1.0, "bytes"]}
	var results: Dictionary = {}
	for name: String in p.get("metrics", []):
		if not metrics.has(name) or (DisplayServer.get_name() == "headless" and name in ["draw_calls", "primitives", "video_memory_bytes"]): return fail("UNSUPPORTED_METRIC", "Metric is unavailable in this runtime: " + name)
		results[name] = {"unit": metrics[name][2], "min": INF, "max": -INF, "sum": 0.0}
	var count: int = 0
	var start: int = Time.get_ticks_msec()
	while count == 0 or Time.get_ticks_msec() - start < int(p.get("duration_ms", 1000)):
		await get_tree().process_frame
		for name: String in results:
			var value: float = Performance.get_monitor(metrics[name][0]) * metrics[name][1]
			results[name].min = minf(results[name].min, value)
			results[name].max = maxf(results[name].max, value)
			results[name].sum += value
		count += 1
	for name: String in results:
		results[name].mean = results[name].sum / count
		results[name].erase("sum")
	return {"metrics": results, "samples": count, "elapsed_ms": Time.get_ticks_msec() - start, "conditions": {"display": DisplayServer.get_name(), "renderer": RenderingServer.get_current_rendering_method(), "engine": Engine.get_version_info().string, "monitor_cadence": "Engine Performance monitors sampled each process frame"}}
