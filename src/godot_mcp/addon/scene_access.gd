@tool
extends RefCounted
## Scene identities survive activation; Node references need to be reacquired.
var host: EditorPlugin

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func find(uri: String = "") -> Node:
	if uri.is_empty(): return EditorInterface.get_edited_scene_root()
	for root: Node in EditorInterface.get_open_scene_roots():
		if is_instance_valid(root) and root.scene_file_path == uri: return root
	return null

func active_path() -> String:
	var root: Node = find()
	return root.scene_file_path if is_instance_valid(root) else ""

func activate(uri: String) -> Dictionary:
	if uri.is_empty() or not host.paths_safe(uri) or not ResourceLoader.exists(uri, "PackedScene"):
		return host.fail("SCENE_NOT_FOUND", "Scene cannot be opened.", {"scene": uri})
	if active_path() != uri:
		EditorInterface.open_scene_from_path(uri)
		await host.get_tree().process_frame
	var actual: String = active_path()
	var result: Dictionary = {"scene": uri, "requested_scene": uri, "active_scene": actual, "opened": find(uri) != null, "active": actual == uri}
	if actual != uri:
		return host.fail("SCENE_NOT_ACTIVE", "The requested scene is not active; inspect the reported scene before retrying.", result)
	return result

func selection() -> Array:
	var refs: Array = []
	for node: Node in EditorInterface.get_selection().get_selected_nodes():
		if is_instance_valid(node): refs.append(host.node_ref(node))
	return refs

func _scene_paths(value: Variant, paths: Array) -> void:
	if value is Dictionary:
		for key: String in value:
			if key == "scene" and value[key] is String and str(value[key]).begins_with("res://"):
				if value[key] not in paths: paths.append(value[key])
			else: _scene_paths(value[key], paths)
	elif value is Array:
		for item: Variant in value: _scene_paths(item, paths)

func enter(p: Dictionary) -> Dictionary:
	var paths: Array = []
	_scene_paths(p, paths)
	var previous: Dictionary = {"scene": active_path(), "selection": selection(), "target": ""}
	if paths.is_empty(): return previous
	# Open prerequisites before resolving any mutation objects; activate the
	# first (destination) scene last, including cross-scene duplicate sources.
	for uri: String in paths:
		if find(uri) == null:
			var opened: Dictionary = await activate(uri)
			if opened.has("error"): return opened
	var activated: Dictionary = await activate(paths[0])
	if activated.has("error"): return activated
	previous.target = paths[0]
	previous.expected_selection = selection()
	return previous

func leave(previous: Dictionary) -> void:
	if previous.get("target", "").is_empty() or previous.scene.is_empty() or previous.scene == previous.target: return
	# A user navigating during the operation owns the new view.
	if active_path() != previous.target or selection() != previous.get("expected_selection", []): return
	if find(previous.scene) == null: return
	var restored: Dictionary = await activate(previous.scene)
	if restored.has("error"): return
	var selected := EditorInterface.get_selection()
	selected.clear()
	for ref: Dictionary in previous.selection:
		var node: Node = host.resolve_node(ref)
		if is_instance_valid(node): selected.add_node(node)
