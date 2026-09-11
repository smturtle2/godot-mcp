@tool
extends RefCounted
## Editor capture owns view framing; shared image encoding owns pixel geometry.
const CaptureImage = preload("res://addons/godot_mcp/capture_image.gd")
var host: EditorPlugin

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func _windows() -> Array[Window]:
	var main: Window = EditorInterface.get_base_control().get_window()
	var found: Array[Window] = [main]
	for node: Node in host.get_tree().root.find_children("*", "Window", true, false):
		if node is Window and node != main and node.visible and not node.is_embedded(): found.append(node)
	return found

func windows() -> Array:
	var result: Array = []
	for window: Window in _windows():
		result.append({"window_id": window.get_window_id(), "title": window.title, "main": window == EditorInterface.get_base_control().get_window(), "size": host.encode(window.size), "embedded": window.is_embedded()})
	return result

func _targets(framing: String, root: Node) -> Array:
	if framing != "selection": return [root]
	var result: Array = []
	for node: Node in EditorInterface.get_selection().get_selected_nodes():
		if is_instance_valid(node) and (node == root or root.is_ancestor_of(node)): result.append(node)
	return result

func _bounds_2d(targets: Array) -> Dictionary:
	var pending: Array = targets.duplicate()
	var bounds := Rect2()
	var found: bool = false
	var unknown: Array = []
	var count: int = 0
	while not pending.is_empty() and count < 10000:
		var node: Node = pending.pop_back()
		count += 1
		pending.append_array(node.get_children())
		if node is CanvasLayer and not node.follow_viewport_enabled:
			unknown.append(host.node_ref(node))
		if not node is CanvasItem or not node.is_visible_in_tree(): continue
		var rect := Rect2()
		var known: bool = true
		if node is Control: rect = Rect2(Vector2.ZERO, node.size)
		elif node is Sprite2D or node is AnimatedSprite2D: rect = node.get_rect()
		elif node is Polygon2D or node is Line2D:
			var points: PackedVector2Array = node.polygon if node is Polygon2D else node.points
			if not points.is_empty():
				rect = Rect2(points[0], Vector2.ZERO)
				for point: Vector2 in points: rect = rect.expand(point)
				if node is Line2D: rect = rect.grow(node.width * 0.5)
		elif node is TileMapLayer and node.tile_set:
			var used: Rect2i = node.get_used_rect()
			if used.has_area():
				var a: Vector2 = node.map_to_local(used.position)
				var b: Vector2 = node.map_to_local(used.end - Vector2i.ONE)
				rect = Rect2(a, Vector2.ZERO).expand(b).grow(float(maxi(node.tile_set.tile_size.x, node.tile_set.tile_size.y)))
		else: known = false
		var script: Script = node.get_script() as Script
		if script:
			for method: Dictionary in script.get_script_method_list():
				if method.name == "_draw": unknown.append(host.node_ref(node))
		if known and rect.has_area():
			rect = node.get_global_transform() * rect
			bounds = bounds.merge(rect) if found else rect
			found = true
	return {"bounds": bounds, "found": found, "unknown": unknown, "truncated": not pending.is_empty()}

func _bounds_3d(targets: Array) -> Dictionary:
	var pending: Array = targets.duplicate()
	var bounds := AABB()
	var found: bool = false
	var count: int = 0
	while not pending.is_empty() and count < 10000:
		var node: Node = pending.pop_back()
		count += 1
		pending.append_array(node.get_children())
		if node is VisualInstance3D and node.is_visible_in_tree():
			var area: AABB = node.global_transform * node.get_aabb()
			bounds = bounds.merge(area) if found else area
			found = true
	return {"bounds": bounds, "found": found, "truncated": not pending.is_empty()}

func capture(p: Dictionary) -> Dictionary:
	if DisplayServer.get_name() == "headless": return host.fail("RENDERER_UNAVAILABLE", "Use a rendered editor session for capture.")
	var kind: String = p.get("viewport", {}).get("kind", "editor_2d")
	var previous: String = host.main_screen
	var screen: String = "2D" if kind == "editor_2d" else "3D" if kind == "editor_3d" else ""
	if not screen.is_empty() and screen != previous:
		EditorInterface.set_main_screen_editor(screen)
		await host.get_tree().process_frame
		await host.get_tree().process_frame
	var result: Dictionary = await _capture(p)
	if not screen.is_empty() and not previous.is_empty() and previous != screen and host.main_screen == screen:
		EditorInterface.set_main_screen_editor(previous)
	return result

func _capture(p: Dictionary) -> Dictionary:
	var spec: Dictionary = p.get("viewport", {})
	var kind: String = spec.get("kind", "editor_2d")
	var framing: String = p.get("framing", "current")
	var requested_scene: String = spec.get("scene", "")
	if framing == "current" and (p.has("bounds_2d") or p.has("bounds_3d")): return host.fail("INVALID_FRAMING", "Explicit bounds require scene or selection framing.")
	if (kind == "editor_2d" and p.has("bounds_3d")) or (kind == "editor_3d" and p.has("bounds_2d")): return host.fail("INVALID_BOUNDS", "Bounds must match the requested editor dimension.")
	if not requested_scene.is_empty() and requested_scene != host.scene_access.active_path():
		return host.fail("SCENE_NOT_ACTIVE", "Activate the requested scene before capturing it.", {"requested_scene": requested_scene, "active_scene": host.scene_access.active_path()})
	if kind == "editor_window" and (framing != "current" or p.has("bounds_2d") or p.has("bounds_3d")):
		return host.fail("INVALID_FRAMING", "Editor windows capture their current visible UI; use an editor viewport to frame scene content.")
	var viewport: Viewport
	var window_id: int = -1
	if kind == "editor_window":
		var available: Array[Window] = _windows()
		window_id = int(spec.get("window_id", available[0].get_window_id()))
		for window: Window in available:
			if window.get_window_id() == window_id: viewport = window
		if not viewport: return host.fail("WINDOW_NOT_FOUND", "Choose a current editor window ID.", {"windows": windows()})
	elif kind == "editor_2d": viewport = EditorInterface.get_editor_viewport_2d()
	elif kind == "editor_3d": viewport = EditorInterface.get_editor_viewport_3d(int(spec.get("index", 0)))
	else: return host.fail("INVALID_VIEWPORT", "Choose an editor window, 2D viewport or 3D viewport.")
	if viewport.get_visible_rect().size.x <= 8 or viewport.get_visible_rect().size.y <= 8: return host.fail("VIEWPORT_UNAVAILABLE", "The selected editor viewport has no usable rendered area.")
	var root: Node = EditorInterface.get_edited_scene_root()
	var scene: String = host.scene_access.active_path()
	var before_2d: Transform2D = viewport.global_canvas_transform
	var desired_2d: Transform2D = before_2d
	var camera: Camera3D = viewport.get_camera_3d() if kind == "editor_3d" else null
	var before_3d: Dictionary = {"transform": camera.global_transform, "size": camera.size, "far": camera.far} if camera else {}
	var desired_3d: Dictionary = before_3d.duplicate()
	var framing_info: Dictionary = {"mode": framing}
	if framing != "current":
		if not is_instance_valid(root): return host.fail("SCENE_NOT_FOUND", "There is no active scene to frame.")
		var targets: Array = _targets(framing, root)
		if targets.is_empty(): return host.fail("EMPTY_SELECTION", "Select nodes in the active scene before framing the selection.")
		var size: Vector2 = viewport.get_visible_rect().size
		if kind == "editor_2d":
			var measured: Dictionary = _bounds_2d(targets)
			var bounds: Rect2 = measured.bounds
			if p.has("bounds_2d"):
				bounds = Rect2(host.Codec.v2(p.bounds_2d.origin), host.Codec.v2(p.bounds_2d.size))
			elif not measured.found or not measured.unknown.is_empty() or measured.truncated:
				return host.fail("BOUNDS_REQUIRED", "Provide bounds_2d for custom drawing, fixed CanvasLayers or unavailable content bounds.", {"unknown": measured.unknown, "truncated": measured.truncated})
			if not bounds.has_area(): return host.fail("INVALID_BOUNDS", "Framing bounds must have positive size.")
			var zoom: float = minf(size.x / bounds.size.x, size.y / bounds.size.y) * 0.9
			desired_2d = Transform2D(Vector2(zoom, 0), Vector2(0, zoom), size * 0.5 - bounds.get_center() * zoom)
			framing_info.bounds = host.encode(bounds)
		elif camera:
			var measured: Dictionary = _bounds_3d(targets)
			var bounds: AABB = measured.bounds
			if p.has("bounds_3d"): bounds = AABB(host.Codec.v3(p.bounds_3d.position), host.Codec.v3(p.bounds_3d.size))
			elif not measured.found or measured.truncated: return host.fail("BOUNDS_REQUIRED", "Provide bounds_3d when visual bounds are unavailable.")
			if bounds.size.x < 0 or bounds.size.y < 0 or bounds.size.z < 0: return host.fail("INVALID_BOUNDS", "3D bounds cannot have negative sizes.")
			var radius: float = maxf(bounds.size.length() * 0.5 * 1.1, 0.01)
			var projection: Projection = camera.get_camera_projection()
			var distance: float
			if camera.projection == Camera3D.PROJECTION_ORTHOGONAL:
				desired_3d.size = camera.size * radius / minf(absf(1.0 / projection.x.x), absf(1.0 / projection.y.y))
				distance = radius + camera.near + 1.0
			else:
				var angle: float = minf(atan(absf(1.0 / projection.x.x)), atan(absf(1.0 / projection.y.y)))
				distance = radius / sin(angle) + camera.near
			desired_3d.transform = Transform3D(camera.global_basis, bounds.get_center() + camera.global_basis.z * distance)
			desired_3d.far = maxf(camera.far, distance + radius + 1.0)
			framing_info.bounds = {"position": host.encode(bounds.position), "size": host.encode(bounds.size)}
		else: return host.fail("CAMERA_UNAVAILABLE", "The 3D editor camera is unavailable.")
	# Set only the render view for this frame, after editor navigation updates.
	# Scene nodes, layout and tool scripts are never duplicated or re-entered.
	await RenderingServer.frame_pre_draw
	if not is_instance_valid(viewport) or host.scene_access.active_path() != scene: return host.fail("CAPTURE_STALE", "The editor view changed before capture.")
	if framing != "current":
		if kind == "editor_2d":
			before_2d = viewport.global_canvas_transform
			viewport.global_canvas_transform = desired_2d
		elif camera:
			before_3d = {"transform": camera.global_transform, "size": camera.size, "far": camera.far}
			camera.global_transform = desired_3d.transform
			camera.force_update_transform()
			camera.size = desired_3d.size
			camera.far = desired_3d.far
	await RenderingServer.frame_post_draw
	var result: Dictionary
	if is_instance_valid(viewport):
		var metadata: Dictionary = {"uri": "godot://captures/editor/" + host.epoch + "/" + str(Time.get_ticks_usec()) + ".png", "kind": kind, "editor_epoch": host.epoch, "scene": host.scene_access.active_path(), "main_screen": host.main_screen, "captured_at": Time.get_datetime_string_from_system(true), "observed_at_usec": Time.get_ticks_usec(), "frame": Engine.get_process_frames(), "selected_nodes": host.scene_access.selection(), "framing": framing_info, "context_matches": scene == host.scene_access.active_path(), "input_supported": false}
		var inspected: Object = EditorInterface.get_inspector().get_edited_object()
		metadata.inspector_target = host.node_ref(inspected) if inspected is Node else host.encode(inspected)
		if kind == "editor_2d": metadata.view = {"canvas_transform": host.encode(viewport.global_canvas_transform)}
		if camera and is_instance_valid(camera): metadata.view = {"transform": host.encode(camera.global_transform), "projection": camera.projection, "fov": camera.fov, "size": camera.size, "near": camera.near, "far": camera.far}
		if kind == "editor_window":
			metadata.window_id = window_id
			metadata.windows = windows()
			metadata.coverage = "Selected Godot window client area; OS borders and other native windows are excluded. Embedded subwindows are included."
		result = CaptureImage.pack(viewport.get_texture().get_image(), p, metadata, viewport.get_visible_rect().size)
	else: result = host.fail("CAPTURE_STALE", "The captured viewport was closed.")
	if framing != "current":
		if is_instance_valid(viewport) and kind == "editor_2d" and viewport.global_canvas_transform == desired_2d: viewport.global_canvas_transform = before_2d
		if is_instance_valid(camera) and camera.global_transform == desired_3d.transform and camera.size == desired_3d.size and camera.far == desired_3d.far:
			camera.global_transform = before_3d.transform
			camera.force_update_transform()
			camera.size = before_3d.size
			camera.far = before_3d.far
	return result
