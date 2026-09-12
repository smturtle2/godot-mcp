@tool
extends RefCounted
var host: EditorPlugin
var run_id: String = ""
var ready: bool = false
var runtime_info: Dictionary = {}
var starting: bool = false
const EditorCaptures = preload("res://addons/godot_mcp/editor_captures.gd")
var editor_captures: RefCounted
const SourceManifest = preload("res://addons/godot_mcp/source_manifest.gd")
var expected_sources: Dictionary = {}
var startup_sources: Dictionary = {}
var startup_token: String = ""
var startup_state: String = "unverified"
var launch_changed_uris: Array = []

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host
	editor_captures = EditorCaptures.new(host)

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

func source_state(uris: Array = [], observed: Dictionary = {}) -> Dictionary:
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
		var captured: Dictionary = SourceManifest.capture(startup_sources.files.keys(), false)
		current = captured.files
		complete = complete and captured.complete
		var overlays: Dictionary = host.documents.store.overlays()
		for uri: String in overlays:
			if original.has(uri): current[uri] = str(overlays[uri]).sha256_text()
	else:
		original = {}
		for uri: String in uris:
			if not startup_sources.files.has(uri): continue
			original[uri] = startup_sources.files.get(uri)
			var info: Dictionary = host.documents.source_info(uri)
			current[uri] = info.get("revision")
			if info.has("error") or info.get("external_change", false): complete = false
	var changed: Array = SourceManifest.differences(original, current)
	if uris.is_empty():
		for uri: String in EditorInterface.get_unsaved_scenes():
			if original.has(uri) and uri not in changed: changed.append(uri)
		var settings: Dictionary = host.assets.settings_snapshot()
		if settings.has("error"): complete = false
		elif not settings.saved and "res://project.godot" not in changed: changed.append("res://project.godot")
	var unclassified: Array = []
	for uri: String in uris:
		if not startup_sources.files.has(uri): unclassified.append(uri)
	result.unclassified_uris = unclassified
	result.changed_uris = changed
	result.state = "source_changed" if not changed.is_empty() else "matches_startup" if complete and startup_state == "matched" else "unverified"
	result.restart_required = null if not changed.is_empty() or not unclassified.is_empty() or not complete else false
	result.runtime_impact = "unknown" if not changed.is_empty() or not unclassified.is_empty() else "not_observed"
	result.runtime_script_changes = []
	for uri: String in observed.get("scripts", {}):
		if not uris.is_empty() and uri not in uris: continue
		var info: Dictionary = host.documents.source_info(uri)
		if not info.has("error") and not info.get("external_change", false) and info.revision != observed.scripts[uri]:
			result.runtime_script_changes.append(uri)
	if not result.runtime_script_changes.is_empty():
		result.restart_required = true
		result.runtime_impact = "confirmed"
	result.observed_runtime = not observed.is_empty()
	result.evidence = "Only differing, freshly observed runtime script text confirms a restart need; unobserved resource and dynamic-load effects remain unknown."
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
	for selection: Dictionary in p.get("observe", []):
		if selection.node.get("run_id", "") != run_id: return host.fail("STALE_RUN", "An observation refers to another run.")
	var result: Dictionary = await host.debugger.request(method, p)
	result.run_id = run_id
	if result.get("capture") is Dictionary and result.capture.has("uri"): result.capture.run_id = run_id
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
		if host.documents.resource_storage(host.resources[uri]) == "document" and uri not in uris: uris.append(uri)
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
	if EditorInterface.is_playing_scene() or host.debugger.has_session():
		var stopped: Dictionary = await stop_game({"run_id": run_id})
		if stopped.has("error") or not stopped.get("stopped", false): return stopped
	guard = _guard_revisions(p.get("revisions", {}))
	if not guard.is_empty(): return guard
	pending = _unsaved_documents()
	if pending.has("error"): return pending
	if not pending.uris.is_empty(): return host.fail("UNSAVED_DOCUMENTS", "Documents changed while preparing the run; read and save them explicitly before retrying.", pending)
	run_id = "run-" + host.epoch + "-" + str(Time.get_ticks_usec())
	runtime_info = {}
	expected_sources = SourceManifest.capture(SourceManifest.run_roots(scene))
	startup_sources = {}
	startup_state = "unverified"
	startup_token = Crypto.new().generate_random_bytes(16).hex_encode()
	var request := FileAccess.open(SourceManifest.REQUEST, FileAccess.WRITE)
	if not request: return host.fail("RUN_FAILED", "Cannot write the runtime source provenance request.")
	request.store_string(JSON.stringify({"run_id": run_id, "token": startup_token, "paths": expected_sources.files.keys()}))
	request.close()
	ready = false
	starting = true
	EditorInterface.play_custom_scene(scene)
	# Native play preparation may normalize the current scene on disk even
	# when it was clean. Record those writes, then identify the launched files.
	var launched: Dictionary = SourceManifest.capture(SourceManifest.run_roots(scene))
	launch_changed_uris = SourceManifest.differences(expected_sources.files, launched.files)
	expected_sources = launched
	var deadline: int = Time.get_ticks_msec() + 15000
	while not ready and Time.get_ticks_msec() < deadline: await host.get_tree().process_frame
	starting = false
	DirAccess.remove_absolute(SourceManifest.REQUEST)
	if not ready: return host.fail("RUN_FAILED", "No runtime handshake arrived. Read get_logs for editor errors.", {"run_id": run_id, "playing": EditorInterface.is_playing_scene(), "recovery": {"tool": "get_logs", "arguments": {"kinds": ["error", "warning"]}}})
	return {"run_id": run_id, "scene": scene, "running": EditorInterface.is_playing_scene(), "runtime_connected": ready, "runtime": runtime_info, "source_provenance": source_state()}

func stop_game(p: Dictionary) -> Dictionary:
	if p.get("run_id", "") != run_id: return host.fail("STALE_RUN", "Cannot stop a different run.")
	if not EditorInterface.is_playing_scene() and not host.debugger.has_session():
		ready = false
		return {"run_id": run_id, "stopped": true, "input_released": true}
	if ready and not host.debugger.state().paused: await host.debugger.request("release_input", {})
	EditorInterface.stop_playing_scene()
	await host.get_tree().process_frame
	var deadline: int = Time.get_ticks_msec() + 5000
	# Both the playing flag and socket can clear before the session's stopped
	# signal. Native handling of that signal must finish before a new launch.
	while (EditorInterface.is_playing_scene() or host.debugger.has_session()) and Time.get_ticks_msec() < deadline: await host.get_tree().process_frame
	var stopped: bool = not EditorInterface.is_playing_scene() and not host.debugger.has_session()
	if stopped: ready = false
	return {"run_id": run_id, "stopped": stopped, "input_released": stopped}

func editor_capture(p: Dictionary) -> Dictionary:
	return await editor_captures.capture(p)

func details() -> Dictionary:
	var observed: Dictionary = await host.debugger.request("_source_state", {}) if ready else {}
	var result: Dictionary = source_state([], observed if not observed.has("error") else {})
	if observed.has("error"): result.observation_error = observed.error
	return result
