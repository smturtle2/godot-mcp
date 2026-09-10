@tool
extends RefCounted
var host: EditorPlugin

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func handles(method: String) -> bool:
	return method in ["get_animation", "edit_animation", "edit_animation_graph", "preview_animation"]

func dispatch(method: String, p: Dictionary) -> Dictionary:
	match method:
		"get_animation": return get_animation(p)
		"edit_animation": return edit_animation(p)
		"edit_animation_graph": return edit_graph(p)
		"preview_animation": return await preview(p)
	return host.fail("UNKNOWN_TOOL", method)

func parameters(tree: AnimationTree) -> Dictionary:
	var values: Dictionary = {}
	for prop: Dictionary in tree.get_property_list():
		if str(prop.name).begins_with("parameters/"): values[str(prop.name)] = tree.get(prop.name)
	return values

func graph_info(root: AnimationNode) -> Dictionary:
	if not root: return {}
	var info: Dictionary = {"class": root.get_class()}
	if root is AnimationNodeStateMachine:
		info.states = []
		for name: StringName in root.get_node_list():
			var node: AnimationNode = root.get_node(name)
			info.states.append({"name": str(name), "class": node.get_class(), "animation": str(node.animation) if node is AnimationNodeAnimation else null, "position": host.encode(root.get_node_position(name))})
		info.transitions = []
		for i: int in root.get_transition_count():
			var transition: AnimationNodeStateMachineTransition = root.get_transition(i)
			info.transitions.append({"from": str(root.get_transition_from(i)), "to": str(root.get_transition_to(i)), "condition": str(transition.advance_condition), "expression": transition.advance_expression, "advance_mode": transition.advance_mode, "cross_fade": transition.xfade_time})
	elif root is AnimationNodeBlendTree:
		info.nodes = []
		for name: StringName in root.get_node_list():
			info.nodes.append({"name": str(name), "position": host.encode(root.get_node_position(name)), "node": graph_info(root.get_node(name))})
		info.connections = host.encode(root.get("node_connections"))
	elif root is AnimationNodeAnimation:
		info.animation = str(root.animation)
	elif root is AnimationNodeBlendSpace1D or root is AnimationNodeBlendSpace2D:
		info.points = []
		for i: int in root.get_blend_point_count():
			info.points.append({"position": host.encode(root.get_blend_point_position(i)), "node": graph_info(root.get_blend_point_node(i))})
		info.min = host.encode(root.min_space)
		info.max = host.encode(root.max_space)
	return info

func get_animation(p: Dictionary) -> Dictionary:
	var node: Node = host.resolve_node(p.get("node", {}))
	if node is AnimationTree:
		return {"node": host.node_ref(node), "graph": graph_info(node.tree_root), "parameters": host.encode(parameters(node)), "animation_player": str(node.anim_player), "active": node.active}
	if not node is AnimationPlayer: return host.fail("INVALID_NODE", "Use an AnimationPlayer or AnimationTree.")
	var names: Array = [p.animation] if p.has("animation") else Array(node.get_animation_list())
	var results: Array = []
	for name: String in names:
		if not node.has_animation(name): return host.fail("ANIMATION_NOT_FOUND", "Animation does not exist: " + name)
		var animation: Animation = node.get_animation(name)
		var tracks: Array = []
		for i: int in animation.get_track_count():
			var keys: Array = []
			for k: int in animation.track_get_key_count(i):
				keys.append({"time": animation.track_get_key_time(i, k), "value": host.encode(animation.track_get_key_value(i, k)), "transition": animation.track_get_key_transition(i, k)})
			tracks.append({"index": i, "kind": track_name(animation.track_get_type(i)), "path": str(animation.track_get_path(i)), "keys": keys, "interpolation": animation.track_get_interpolation_type(i), "enabled": animation.track_is_enabled(i), "imported": animation.track_is_imported(i)})
		results.append({"name": name, "resource": host.encode(animation), "length": animation.length, "loop_mode": animation.loop_mode, "tracks": tracks})
	return {"player": host.node_ref(node), "animations": results}

func track_type(kind: String) -> int:
	return {"value": Animation.TYPE_VALUE, "position_3d": Animation.TYPE_POSITION_3D, "rotation_3d": Animation.TYPE_ROTATION_3D, "scale_3d": Animation.TYPE_SCALE_3D, "method": Animation.TYPE_METHOD, "bezier": Animation.TYPE_BEZIER}.get(kind, -1)

func track_name(type: int) -> String:
	return {Animation.TYPE_VALUE: "value", Animation.TYPE_POSITION_3D: "position_3d", Animation.TYPE_ROTATION_3D: "rotation_3d", Animation.TYPE_SCALE_3D: "scale_3d", Animation.TYPE_METHOD: "method", Animation.TYPE_BEZIER: "bezier"}.get(type, str(type))

func set_library(player: AnimationPlayer, name: String, library: AnimationLibrary) -> void:
	if player.has_animation_library(name): player.remove_animation_library(name)
	if library: player.add_animation_library(name, library)

func set_animation(library: AnimationLibrary, name: String, animation: Animation) -> void:
	if library.has_animation(name): library.remove_animation(name)
	if animation: library.add_animation(name, animation)

func edit_animation(p: Dictionary) -> Dictionary:
	var player: AnimationPlayer = host.resolve_node(p.get("player", {})) as AnimationPlayer
	if not player: return host.fail("INVALID_NODE", "player must be an AnimationPlayer.")
	var full_name: String = p.get("name", "")
	var library_name: String = full_name.get_slice("/", 0) if full_name.contains("/") else ""
	var name: String = full_name.get_slice("/", 1) if full_name.contains("/") else full_name
	if name.is_empty() or full_name.count("/") > 1 or name.contains(":") or name.contains(",") or name.contains("["):
		return host.fail("INVALID_NAME", "Animation name must be name or library/name.")
	var original_library: AnimationLibrary = player.get_animation_library(library_name) if player.has_animation_library(library_name) else null
	var original: Animation = original_library.get_animation(name) if original_library and original_library.has_animation(name) else null
	if not original and not p.get("create", false): return host.fail("ANIMATION_NOT_FOUND", "Set create=true to create this animation.")
	var scope: String = p.get("scope", "node")
	if scope == "shared" and original and (original.resource_path.contains(".godot/imported") or FileAccess.file_exists(original.resource_path.get_slice("::", 0) + ".import")):
		return host.fail("IMPORTED_RESOURCE", "Use node scope to preserve an authored copy of an imported animation.")
	var animation: Animation = original.duplicate(true) if original else Animation.new()
	if p.has("length"): animation.length = float(p.length)
	if p.has("loop"): animation.loop_mode = Animation.LOOP_LINEAR if p.loop else Animation.LOOP_NONE
	for spec: Dictionary in p.get("tracks", []):
		var op: String = spec.get("op", "update" if spec.has("index") else "add")
		var index: int = int(spec.get("index", -1))
		if op != "add" and (index < 0 or index >= animation.get_track_count()): return host.fail("INVALID_TRACK", "Track index is outside the animation.")
		if op == "remove":
			animation.remove_track(index)
			continue
		var type: int = track_type(str(spec.get("kind", ""))) if spec.has("kind") else (animation.track_get_type(index) if index >= 0 else -1)
		if type < 0: return host.fail("INVALID_TRACK", "A new track requires a supported kind.")
		if op == "add": index = animation.add_track(type)
		elif animation.track_get_type(index) != type: return host.fail("INVALID_TRACK", "Replace a track to change its kind.")
		if spec.has("path"): animation.track_set_path(index, NodePath(spec.path))
		if spec.has("enabled"): animation.track_set_enabled(index, spec.enabled)
		if spec.has("interpolation"):
			animation.track_set_interpolation_type(index, {"nearest": Animation.INTERPOLATION_NEAREST, "linear": Animation.INTERPOLATION_LINEAR, "cubic": Animation.INTERPOLATION_CUBIC}[spec.interpolation])
		if spec.get("replace_keys", false):
			for old: int in range(animation.track_get_key_count(index) - 1, -1, -1): animation.track_remove_key(index, old)
		for key: Dictionary in spec.get("keys", []):
			var time: float = float(key.get("time", 0))
			if key.get("remove", false):
				var at: int = animation.track_find_key(index, time, Animation.FIND_MODE_APPROX)
				if at >= 0: animation.track_remove_key(index, at)
				continue
			if not key.has("value"): return host.fail("INVALID_KEY", "Keys need a value or remove=true.")
			var value: Variant = host.decode(key.value)
			if type in [Animation.TYPE_POSITION_3D, Animation.TYPE_SCALE_3D] and not value is Vector3: return host.fail("INVALID_KEY", "Position/scale keys require Vector3.")
			if type == Animation.TYPE_ROTATION_3D and not value is Quaternion: return host.fail("INVALID_KEY", "Rotation keys require Quaternion.")
			if type == Animation.TYPE_METHOD and (not value is Dictionary or not value.get("method") is String or not value.get("args", []) is Array): return host.fail("INVALID_KEY", "Method keys require {method, args}.")
			if type == Animation.TYPE_BEZIER:
				if not (value is float or value is int): return host.fail("INVALID_KEY", "Bezier keys require numeric values.")
				animation.bezier_track_insert_key(index, time, float(value))
			else:
				animation.track_insert_key(index, time, value, float(key.get("transition", 1)))
	var root: Node = host.scene_root(p.player.scene)
	host.begin_edit("Edit animation", root)
	var undo: EditorUndoRedoManager = host.get_undo_redo()
	if scope == "shared" and original_library:
		undo.add_do_method(self, "set_animation", original_library, name, animation)
		undo.add_undo_method(self, "set_animation", original_library, name, original)
	else:
		var library: AnimationLibrary = original_library.duplicate(true) if original_library else AnimationLibrary.new()
		set_animation(library, name, animation)
		undo.add_do_method(self, "set_library", player, library_name, library)
		undo.add_undo_method(self, "set_library", player, library_name, original_library)
	var result: Dictionary = host.finish_edit(root, "Edit animation")
	result.animation = full_name
	result.scope = scope
	result.length = animation.length
	result.track_count = animation.get_track_count()
	result.reimport_persistence = "authored library copy in this scene" if scope == "node" else "shared authored library; save all owning documents"
	return result

func make_graph_node(spec: Dictionary) -> Dictionary:
	var node: AnimationNode
	match str(spec.get("kind", "animation")):
		"animation":
			var animation := AnimationNodeAnimation.new()
			animation.animation = str(spec.get("animation", ""))
			node = animation
		"blend2": node = AnimationNodeBlend2.new()
		"add2": node = AnimationNodeAdd2.new()
		"blend3": node = AnimationNodeBlend3.new()
		"one_shot": node = AnimationNodeOneShot.new()
		"time_scale": node = AnimationNodeTimeScale.new()
		"time_seek": node = AnimationNodeTimeSeek.new()
		"blend_space_1d":
			var space := AnimationNodeBlendSpace1D.new()
			if not (spec.get("min", -1) is float or spec.get("min", -1) is int) or not (spec.get("max", 1) is float or spec.get("max", 1) is int): return host.fail("INVALID_GRAPH", "1D blend-space bounds must be numbers.")
			space.min_space = float(spec.get("min", -1))
			space.max_space = float(spec.get("max", 1))
			if space.min_space >= space.max_space: return host.fail("INVALID_GRAPH", "Blend-space min must be less than max.")
			for point: Dictionary in spec.get("points", []):
				if not (point.position is int or point.position is float): return host.fail("INVALID_GRAPH", "1D blend points need numeric positions.")
				var animation := AnimationNodeAnimation.new()
				animation.animation = point.animation
				space.add_blend_point(animation, float(point.position))
			node = space
		"blend_space_2d":
			var space := AnimationNodeBlendSpace2D.new()
			if not spec.get("min", {}) is Dictionary or not spec.get("max", {}) is Dictionary: return host.fail("INVALID_GRAPH", "2D blend-space bounds require vectors.")
			space.min_space = host.Codec.v2(spec.get("min", {"x": -1, "y": -1}))
			space.max_space = host.Codec.v2(spec.get("max", {"x": 1, "y": 1}))
			if space.min_space.x >= space.max_space.x or space.min_space.y >= space.max_space.y: return host.fail("INVALID_GRAPH", "Blend-space bounds must be increasing.")
			for point: Dictionary in spec.get("points", []):
				if not point.position is Dictionary: return host.fail("INVALID_GRAPH", "2D blend points require vectors.")
				var animation := AnimationNodeAnimation.new()
				animation.animation = point.animation
				space.add_blend_point(animation, host.Codec.v2(point.position))
			node = space
		_: return host.fail("INVALID_GRAPH", "Unsupported blend node.")
	if not spec.get("filter", []).is_empty():
		if str(spec.get("kind", "")) not in ["blend2", "add2", "blend3", "one_shot"]: return host.fail("INVALID_GRAPH", "This animation node does not support filters.")
		node.filter_enabled = true
		for path: String in spec.filter: node.set_filter_path(NodePath(path), true)
	return {"node": node}

func apply_graph(tree: AnimationTree, root: AnimationNode, values: Dictionary, active: bool) -> void:
	tree.active = false
	tree.tree_root = root
	for key: String in values:
		if not host.property_info(tree, key).is_empty(): tree.set(key, values[key])
	tree.active = active

func edit_graph(p: Dictionary) -> Dictionary:
	var tree: AnimationTree = host.resolve_node(p.get("tree", {})) as AnimationTree
	if not tree: return host.fail("INVALID_NODE", "tree must be an AnimationTree.")
	var original: AnimationNode = tree.tree_root
	var root: AnimationNode = original.duplicate(true) if original else null
	if p.has("root_type") or not root:
		var desired: String = p.get("root_type", "state_machine")
		if desired == "state_machine" and not root is AnimationNodeStateMachine: root = AnimationNodeStateMachine.new()
		elif desired == "blend_tree" and not root is AnimationNodeBlendTree: root = AnimationNodeBlendTree.new()
	if root is AnimationNodeStateMachine:
		for state: Dictionary in p.get("states", []):
			var name: String = state.get("name", "")
			if name.is_empty() or name in ["Start", "End"] or name.contains("/"): return host.fail("INVALID_GRAPH", "Invalid or reserved state name.")
			if state.get("remove", false):
				if root.has_node(name): root.remove_node(name)
				continue
			if not state.has("animation"): return host.fail("INVALID_GRAPH", "States need an animation.")
			var node := AnimationNodeAnimation.new()
			node.animation = state.animation
			if root.has_node(name): root.replace_node(name, node)
			else: root.add_node(name, node, host.Codec.v2(state.get("position", {})))
		for spec: Dictionary in p.get("transitions", []):
			var from: String = spec.get("from", "")
			var to: String = spec.get("to", "")
			if not root.has_node(from) or not root.has_node(to): return host.fail("INVALID_GRAPH", "Transition endpoints do not exist.")
			if root.has_transition(from, to): root.remove_transition(from, to)
			if spec.get("remove", false): continue
			var transition := AnimationNodeStateMachineTransition.new()
			transition.advance_condition = str(spec.get("condition", ""))
			transition.advance_expression = str(spec.get("expression", ""))
			transition.advance_mode = {"auto": AnimationNodeStateMachineTransition.ADVANCE_MODE_AUTO, "enabled": AnimationNodeStateMachineTransition.ADVANCE_MODE_ENABLED, "disabled": AnimationNodeStateMachineTransition.ADVANCE_MODE_DISABLED}.get(spec.get("advance", "enabled"), AnimationNodeStateMachineTransition.ADVANCE_MODE_ENABLED)
			transition.xfade_time = float(spec.get("cross_fade", 0))
			root.add_transition(from, to, transition)
	elif root is AnimationNodeBlendTree:
		for name: String in p.get("remove_nodes", []):
			if name == "output": return host.fail("INVALID_GRAPH", "Cannot remove the output node.")
			if root.has_node(name): root.remove_node(name)
		for spec: Dictionary in p.get("nodes", []):
			var name: String = spec.get("name", "")
			if name.is_empty() or name == "output" or name.contains("/"): return host.fail("INVALID_GRAPH", "Invalid blend node name.")
			var made: Dictionary = make_graph_node(spec)
			if made.has("error"): return made
			if root.has_node(name): root.remove_node(name)
			root.add_node(name, made.node, host.Codec.v2(spec.get("position", {})))
		for connection: Dictionary in p.get("connections", []):
			if not root.has_node(connection.to) or not root.has_node(connection.from): return host.fail("INVALID_GRAPH", "Blend connection endpoint is missing.")
			var input: int = int(connection.input)
			if input < 0 or input >= root.get_node(connection.to).get_input_count() or connection.to == connection.from: return host.fail("INVALID_GRAPH", "Blend connection input is invalid.")
			root.disconnect_node(connection.to, input)
			root.connect_node(connection.to, input, connection.from)
	else: return host.fail("UNSUPPORTED_GRAPH", "Use a state-machine or blend-tree root.")
	var before: Dictionary = parameters(tree)
	var probe := AnimationTree.new()
	probe.tree_root = root
	var error: String = host.property_error(probe, p.get("parameters", {}))
	if not error.is_empty():
		probe.free()
		return host.fail("INVALID_PARAMETER", error)
	var after: Dictionary = parameters(probe)
	for key: String in before:
		if after.has(key): after[key] = before[key]
	for key: String in p.get("parameters", {}): after[key] = host.decode(p.parameters[key])
	probe.free()
	host.begin_edit("Edit animation graph", tree)
	host.get_undo_redo().add_do_method(self, "apply_graph", tree, root, after, bool(p.get("active", tree.active)))
	host.get_undo_redo().add_undo_method(self, "apply_graph", tree, original, before, tree.active)
	var result: Dictionary = host.finish_edit(tree, "Edit animation graph")
	result.graph = graph_info(root)
	result.parameters = host.encode(parameters(tree))
	result.scope = "node"
	return result

func preview(p: Dictionary) -> Dictionary:
	var player: AnimationPlayer = host.resolve_node(p.get("player", {})) as AnimationPlayer
	if not player or not player.has_animation(p.get("name", "")): return host.fail("ANIMATION_NOT_FOUND", "Player or animation does not exist.")
	var animation: Animation = player.get_animation(p.name)
	var base: Node = player.get_node_or_null(player.root_node)
	if not base: return host.fail("NODE_NOT_FOUND", "Animation root_node does not exist.")
	var time: float = clampf(float(p.get("time", 0)), 0, animation.length)
	var pose: Array = []
	var skipped: Array = []
	for i: int in animation.get_track_count():
		if not animation.track_is_enabled(i) or animation.track_get_key_count(i) == 0: continue
		var type: int = animation.track_get_type(i)
		if type in [Animation.TYPE_METHOD, Animation.TYPE_AUDIO, Animation.TYPE_ANIMATION]:
			skipped.append(i)
			continue
		var path: NodePath = animation.track_get_path(i)
		var node: Node = base.get_node_or_null(NodePath(path.get_concatenated_names()))
		if not node: return host.fail("NODE_NOT_FOUND", "Animation target is missing: " + str(path))
		var property: String = str(path.get_concatenated_subnames())
		var value: Variant
		match type:
			Animation.TYPE_VALUE: value = animation.value_track_interpolate(i, time)
			Animation.TYPE_POSITION_3D:
				if not node is Node3D or not property.is_empty(): return host.fail("UNSUPPORTED_PREVIEW", "3D bone tracks are not previewed; use a Node3D transform target.")
				property = "position"
				value = animation.position_track_interpolate(i, time)
			Animation.TYPE_ROTATION_3D:
				if not node is Node3D or not property.is_empty(): return host.fail("UNSUPPORTED_PREVIEW", "Rotation preview requires a Node3D target.")
				property = "quaternion"
				value = animation.rotation_track_interpolate(i, time)
			Animation.TYPE_SCALE_3D:
				if not node is Node3D or not property.is_empty(): return host.fail("UNSUPPORTED_PREVIEW", "Scale preview requires a Node3D target.")
				property = "scale"
				value = animation.scale_track_interpolate(i, time)
			Animation.TYPE_BEZIER: value = animation.bezier_track_interpolate(i, time)
			_:
				skipped.append(i)
				continue
		if property.is_empty() or host.property_info(node, property.get_slice(":", 0)).is_empty(): return host.fail("PROPERTY_NOT_FOUND", "Animation property does not exist: " + property)
		pose.append({"node": node, "property": NodePath(property), "before": node.get_indexed(NodePath(property)), "after": value})
	for item: Dictionary in pose: item.node.set_indexed(item.property, item.after)
	await host.get_tree().process_frame
	var capture: Dictionary = {}
	if p.get("capture", true): capture = await host.runtime.editor_capture({"viewport": {"kind": p.get("viewport", "editor_2d")}})
	for item: Dictionary in pose: item.node.set_indexed(item.property, item.before)
	var result: Dictionary = {"animation": p.name, "time": time, "restored": true, "pose": [], "skipped_effect_tracks": skipped}
	for item: Dictionary in pose: result.pose.append({"node": host.node_ref(item.node), "property": str(item.property), "value": host.encode(item.after)})
	if p.get("capture", true): result.capture = capture
	return result
