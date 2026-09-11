@tool
extends RefCounted
var host: EditorPlugin
var run_id: String = ""
var ready: bool = false
var runtime_info: Dictionary = {}
var starting: bool = false

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func handles(method: String) -> bool:
	return method in ["run_scene", "stop_game", "inspect_runtime", "capture_viewport", "wait_for_condition", "sample_performance", "send_input"]

func on_ready(info: Dictionary) -> void:
	if not starting or run_id.is_empty(): run_id = "run-" + host.epoch + "-" + str(Time.get_ticks_usec())
	runtime_info = info
	ready = true

func dispatch(method: String, p: Dictionary) -> Dictionary:
	if method == "run_scene": return await run_scene(p)
	if method == "stop_game": return await stop_game(p)
	if method == "capture_viewport" and p.get("viewport", {}).get("kind", "game") != "game": return await editor_capture(p)
	var requested: String = str(p.get("run_id", p.get("node", {}).get("run_id", p.get("viewport", {}).get("run_id", ""))))
	if requested != run_id or not ready or not EditorInterface.is_playing_scene(): return host.fail("STALE_RUN", "The requested run is not active.")
	for key: String in ["condition", "wait_for"]:
		if p.has(key):
			var condition: Dictionary = p[key]
			if condition.has("node") and condition.node.get("node", {}).get("run_id", "") != run_id: return host.fail("STALE_RUN", "The condition refers to another run.")
			if condition.has("property") and condition.property.get("node", {}).get("run_id", "") != run_id: return host.fail("STALE_RUN", "The condition refers to another run.")
			if condition.has("signal") and condition.signal.get("node", {}).get("run_id", "") != run_id: return host.fail("STALE_RUN", "The condition refers to another run.")
	var result: Dictionary = await host.debugger.request(method, p)
	result.run_id = run_id
	return result

func run_scene(p: Dictionary) -> Dictionary:
	if EditorInterface.is_playing_scene():
		if not p.get("restart", false): return host.fail("ALREADY_RUNNING", "Stop the game or pass restart=true.")
		var stopped: Dictionary = await stop_game({"run_id": run_id})
		if stopped.has("error") or not stopped.get("stopped", false): return stopped
	var scene: String = p.get("scene", str(ProjectSettings.get_setting("application/run/main_scene", "")))
	if scene.begins_with("uid://"):
		var uid: int = ResourceUID.text_to_id(scene)
		if ResourceUID.has_id(uid): scene = ResourceUID.get_id_path(uid)
	if scene.is_empty() or not FileAccess.file_exists(scene): return host.fail("SCENE_NOT_FOUND", "Choose an existing scene or configure the project main scene.")
	var unsaved: Array = Array(EditorInterface.get_unsaved_scenes()) + Array(EditorInterface.get_script_editor().get_unsaved_files())
	for uri: String in host.documents.dirty_uris():
		if not uri in unsaved: unsaved.append(uri)
	for uri: String in host.dirty_resources():
		if uri.begins_with("res://") and not uri.contains("::") and not uri in unsaved: unsaved.append(uri)
	if not unsaved.is_empty():
		if not p.get("save", false): return host.fail("UNSAVED_DOCUMENTS", "Save edited documents or pass save=true.", {"uris": unsaved})
		var saved: Dictionary = await host.documents.save_documents({"uris": unsaved})
		if not saved.complete: return host.fail("SAVE_FAILED", "Some documents could not be saved before running.", saved)
	run_id = "run-" + host.epoch + "-" + str(Time.get_ticks_usec())
	ready = false
	starting = true
	EditorInterface.play_custom_scene(scene)
	var deadline: int = Time.get_ticks_msec() + 15000
	while not ready and Time.get_ticks_msec() < deadline: await host.get_tree().process_frame
	starting = false
	if not ready: return host.fail("RUN_FAILED", "No runtime handshake arrived. Inspect editor diagnostics.", {"run_id": run_id, "playing": EditorInterface.is_playing_scene()})
	return {"run_id": run_id, "scene": scene, "running": EditorInterface.is_playing_scene(), "runtime_connected": ready, "runtime": runtime_info}

func stop_game(p: Dictionary) -> Dictionary:
	if p.get("run_id", "") != run_id: return host.fail("STALE_RUN", "Cannot stop a different run.")
	if not EditorInterface.is_playing_scene(): return {"run_id": run_id, "stopped": true, "input_released": true}
	if ready and not host.debugger.state().paused: await host.debugger.request("release_input", {})
	EditorInterface.stop_playing_scene()
	var deadline: int = Time.get_ticks_msec() + 5000
	while EditorInterface.is_playing_scene() and Time.get_ticks_msec() < deadline: await host.get_tree().process_frame
	var stopped: bool = not EditorInterface.is_playing_scene()
	if stopped: ready = false
	return {"run_id": run_id, "stopped": stopped, "input_released": stopped}

func editor_capture(p: Dictionary) -> Dictionary:
	if DisplayServer.get_name() == "headless": return host.fail("RENDERER_UNAVAILABLE", "Use a rendered editor session for viewport capture.")
	var kind: String = p.get("viewport", {}).get("kind", "editor_2d")
	var viewport: SubViewport = EditorInterface.get_editor_viewport_3d(int(p.get("viewport", {}).get("index", 0))) if kind == "editor_3d" else EditorInterface.get_editor_viewport_2d()
	await RenderingServer.frame_post_draw
	var image: Image = viewport.get_texture().get_image()
	if not image or image.is_empty(): return host.fail("CAPTURE_FAILED", "Viewport returned no image.")
	var original: Vector2i = image.get_size()
	var rect := Rect2i(Vector2i.ZERO, original)
	if p.has("rect"):
		rect = Rect2i(Vector2i(host.Codec.v2(p.rect.origin)), Vector2i(host.Codec.v2(p.rect.size))).intersection(rect)
		if not rect.has_area(): return host.fail("INVALID_RECT", "Crop rectangle is outside the viewport.")
		image = image.get_region(rect)
	var scale: float = minf(1.0, minf(float(p.get("max_width", 1280)) / image.get_width(), float(p.get("max_height", 1280)) / image.get_height()))
	if scale < 1: image.resize(maxi(1, int(image.get_width() * scale)), maxi(1, int(image.get_height() * scale)))
	return {"image_base64": Marshalls.raw_to_base64(image.save_png_to_buffer()), "width": image.get_width(), "height": image.get_height(), "viewport_size": host.encode(original), "crop": host.encode(rect), "kind": kind, "frame": Engine.get_process_frames()}
