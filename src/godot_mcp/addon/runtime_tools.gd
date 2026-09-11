@tool
extends RefCounted
var host: EditorPlugin
var run_id: String = ""
var ready: bool = false
var runtime_info: Dictionary = {}
var starting: bool = false
const SourceManifest = preload("res://addons/godot_mcp/source_manifest.gd")
var expected_sources: Dictionary = {}
var startup_sources: Dictionary = {}
var startup_token: String = ""
var startup_state: String = "unverified"
var launch_changed_uris: Array = []

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func handles(method: String) -> bool:
	return method in ["run_scene", "stop_game", "inspect_runtime", "capture_viewport", "wait_for_condition", "sample_performance", "send_input"]

func on_ready(info: Dictionary) -> bool:
	var proof: Dictionary = info.get("source_startup", {})
	if not starting or run_id.is_empty():
		run_id = "run-" + host.epoch + "-" + str(Time.get_ticks_usec())
		expected_sources = {}
		startup_sources = {}
		startup_state = "unverified"
	elif proof.get("run_id") == run_id and proof.get("token") == startup_token:
		startup_sources = proof.get("observed", {})
		startup_state = "matched" if expected_sources.get("complete", false) and startup_sources.get("complete", false) and startup_sources.get("files") == expected_sources.get("files") else "mismatched" if startup_sources.get("complete", false) else "unavailable"
	else:
		return false
	runtime_info = info
	runtime_info.erase("source_startup")
	ready = true
	return true

func source_state(uris: Array = []) -> Dictionary:
	var result: Dictionary = {"run_id": run_id, "running": EditorInterface.is_playing_scene(), "state": "unverified", "startup_files": startup_state, "behavior": "unverified", "scope": SourceManifest.SCOPE}
	if not result.running:
		result.state = "not_running"
		return result
	if not ready or startup_sources.is_empty(): return result
	result.source_snapshot_id = startup_sources.snapshot_id
	result.startup_changed_uris = SourceManifest.differences(expected_sources.get("files", {}), startup_sources.files)
	result.launch_changed_uris = launch_changed_uris
	var current: Dictionary = {}
	var original: Dictionary = startup_sources.files
	var complete: bool = startup_sources.complete
	if uris.is_empty():
		var captured: Dictionary = SourceManifest.capture()
		current = captured.files
		complete = complete and captured.complete
		var overlays: Dictionary = host.documents.store.overlays()
		for uri: String in overlays: current[uri] = str(overlays[uri]).sha256_text()
	else:
		original = {}
		for uri: String in uris:
			original[uri] = startup_sources.files.get(uri)
			var info: Dictionary = host.documents.source_info(uri)
			current[uri] = info.get("revision")
			if info.has("error") or info.get("external_change", false): complete = false
	var changed: Array = SourceManifest.differences(original, current)
	if uris.is_empty():
		for uri: String in EditorInterface.get_unsaved_scenes():
			if uri not in changed: changed.append(uri)
		var settings: Dictionary = host.assets.settings_snapshot()
		if settings.has("error"): complete = false
		elif not settings.saved and "res://project.godot" not in changed: changed.append("res://project.godot")
	result.changed_uris = changed
	result.state = "source_changed" if not changed.is_empty() else "matches_startup" if complete and startup_state == "matched" else "unverified"
	result.restart_required = not changed.is_empty()
	result.evidence = "Startup file hashes identify observed files, not which scripts executed. Runtime observations cover only the requested properties, input or conditions."
	return result

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
	result.source_provenance = source_state()
	return result

func _guard_revisions(revisions: Dictionary) -> Dictionary:
	for uri: String in revisions:
		var info: Dictionary = host.documents.source_info(uri)
		if info.has("error"): return info
		if info.external_change or info.revision != revisions[uri]: return host.fail("REVISION_CONFLICT", "Run requires the current accepted source revisions.", {"uri": uri, "expected_revision": revisions[uri], "current_revision": info.revision})
	return {}

func _unsaved_documents() -> Dictionary:
	var uris: Array = Array(EditorInterface.get_unsaved_scenes()) + Array(EditorInterface.get_script_editor().get_unsaved_files())
	for uri: String in host.documents.dirty_uris():
		if uri not in uris: uris.append(uri)
	for uri: String in host.dirty_resources():
		if uri.begins_with("res://") and not uri.contains("::") and uri not in uris: uris.append(uri)
	var settings: Dictionary = host.assets.settings_snapshot()
	if settings.has("error"): return settings
	if not settings.saved and "res://project.godot" not in uris: uris.append("res://project.godot")
	return {"uris": uris}

func run_scene(p: Dictionary) -> Dictionary:
	var guard: Dictionary = _guard_revisions(p.get("revisions", {}))
	if not guard.is_empty(): return guard
	if EditorInterface.is_playing_scene() and not p.get("restart", false): return host.fail("ALREADY_RUNNING", "Stop the game or pass restart=true.")
	var scene: String = p.get("scene", str(ProjectSettings.get_setting("application/run/main_scene", "")))
	if scene.begins_with("uid://"):
		var uid: int = ResourceUID.text_to_id(scene)
		if ResourceUID.has_id(uid): scene = ResourceUID.get_id_path(uid)
	if scene.is_empty() or not FileAccess.file_exists(scene): return host.fail("SCENE_NOT_FOUND", "Choose an existing scene or configure the project main scene.")
	var pending: Dictionary = _unsaved_documents()
	if pending.has("error"): return pending
	var unsaved: Array = pending.uris
	var save_uris: Array = p.get("save_uris", [])
	var unrequested: Array = unsaved.filter(func(uri: String) -> bool: return uri not in save_uris)
	if not unrequested.is_empty(): return host.fail("UNSAVED_DOCUMENTS", "Save or reconcile these documents explicitly before play, or include their paths in save_uris.", {"uris": unrequested})
	if not save_uris.is_empty():
		var saved: Dictionary = await host.documents.save_documents({"uris": save_uris})
		if saved.has("error"): return saved
		if not saved.complete: return host.fail("SAVE_FAILED", "Some explicitly requested documents could not be saved before running.", saved)
	guard = _guard_revisions(p.get("revisions", {}))
	if not guard.is_empty(): return guard
	if EditorInterface.is_playing_scene() or host.debugger.state().active:
		var stopped: Dictionary = await stop_game({"run_id": run_id})
		if stopped.has("error") or not stopped.get("stopped", false): return stopped
	guard = _guard_revisions(p.get("revisions", {}))
	if not guard.is_empty(): return guard
	pending = _unsaved_documents()
	if pending.has("error"): return pending
	if not pending.uris.is_empty(): return host.fail("UNSAVED_DOCUMENTS", "Documents changed while preparing the run; read and save them explicitly before retrying.", pending)
	run_id = "run-" + host.epoch + "-" + str(Time.get_ticks_usec())
	expected_sources = SourceManifest.capture()
	startup_sources = {}
	startup_state = "unverified"
	startup_token = Crypto.new().generate_random_bytes(16).hex_encode()
	var request := FileAccess.open(SourceManifest.REQUEST, FileAccess.WRITE)
	if not request: return host.fail("RUN_FAILED", "Cannot write the runtime source provenance request.")
	request.store_string(JSON.stringify({"run_id": run_id, "token": startup_token}))
	request.close()
	ready = false
	starting = true
	EditorInterface.play_custom_scene(scene)
	# Native play preparation may normalize the current scene on disk even
	# when it was clean. Record those writes, then identify the launched files.
	var launched: Dictionary = SourceManifest.capture()
	launch_changed_uris = SourceManifest.differences(expected_sources.files, launched.files)
	expected_sources = launched
	var deadline: int = Time.get_ticks_msec() + 15000
	while not ready and Time.get_ticks_msec() < deadline: await host.get_tree().process_frame
	starting = false
	DirAccess.remove_absolute(SourceManifest.REQUEST)
	if not ready: return host.fail("RUN_FAILED", "No runtime handshake arrived. Inspect editor diagnostics.", {"run_id": run_id, "playing": EditorInterface.is_playing_scene()})
	return {"run_id": run_id, "scene": scene, "running": EditorInterface.is_playing_scene(), "runtime_connected": ready, "runtime": runtime_info, "source_provenance": source_state()}

func stop_game(p: Dictionary) -> Dictionary:
	if p.get("run_id", "") != run_id: return host.fail("STALE_RUN", "Cannot stop a different run.")
	if not EditorInterface.is_playing_scene() and not host.debugger.state().active:
		ready = false
		return {"run_id": run_id, "stopped": true, "input_released": true}
	if ready and not host.debugger.state().paused: await host.debugger.request("release_input", {})
	EditorInterface.stop_playing_scene()
	await host.get_tree().process_frame
	var deadline: int = Time.get_ticks_msec() + 5000
	# The playing flag can clear before the debugger stop is delivered. Starting
	# again in that gap can cancel the new launch with the previous stop event.
	while (EditorInterface.is_playing_scene() or host.debugger.state().active) and Time.get_ticks_msec() < deadline: await host.get_tree().process_frame
	var stopped: bool = not EditorInterface.is_playing_scene() and not host.debugger.state().active
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
