@tool
extends RefCounted
var host: EditorPlugin

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func handles(method: String) -> bool:
	return method in ["get_scene", "open_scene", "create_scene", "create_nodes", "update_nodes", "delete_nodes", "get_class_info"]

func dispatch(method: String, p: Dictionary) -> Dictionary:
	match method:
		"get_scene": return get_scene(p)
		"open_scene":
			return await host.scene_access.activate(str(p.get("scene", "")))
		"create_scene": return await create_scene(p)
		"create_nodes": return await create_nodes(p)
		"update_nodes": return await update_nodes(p)
		"delete_nodes": return await delete_nodes(p)
		"get_class_info": return class_info(p)
	return host.fail("UNKNOWN_TOOL", method)

func class_info(p: Dictionary) -> Dictionary:
	var cls: String = p.get("class", "")
	var info: Dictionary
	if ClassDB.class_exists(cls):
		info = {"class": cls, "parent": ClassDB.get_parent_class(cls), "instantiable": ClassDB.can_instantiate(cls), "properties": ClassDB.class_get_property_list(cls), "methods": ClassDB.class_get_method_list(cls), "signals": ClassDB.class_get_signal_list(cls)}
	else:
		var uri: String = cls if cls.begins_with("res://") else ""
		for entry: Dictionary in ProjectSettings.get_global_class_list():
			if entry["class"] == cls: uri = entry.path
		var script: Script = host.resource_uri(uri) as Script
		if not script: return host.fail("UNKNOWN_CLASS", "No engine or project script class matches.")
		info = {"class": cls, "uri": uri, "parent": script.get_instance_base_type(), "properties": script.get_script_property_list(), "methods": script.get_script_method_list(), "signals": script.get_script_signal_list()}
	if p.has("member"):
		for category: String in ["properties", "methods", "signals"]:
			var filtered: Array = []
			for item: Dictionary in info[category]:
				if str(item.name) == str(p.member): filtered.append(item)
			info[category] = filtered
	info.engine = Engine.get_version_info().string
	return host.encode(info)

func get_scene(p: Dictionary) -> Dictionary:
	var root: Node = host.scene_root(str(p.get("scene", "")))
	if not root: return host.fail("SCENE_NOT_FOUND", "No matching live scene.")
	var path: String = p.get("path", ".")
	if path.begins_with("/") or ".." in path.split("/"): return host.fail("INVALID_PATH", "Node path must be relative to the scene root.")
	var start: Node = root.get_node_or_null(NodePath(path))
	if not start: return host.fail("NODE_NOT_FOUND", "Node does not exist in this scene.")
	var include: Array = p.get("include", [])
	var names: Array = p.get("properties", []) if p.has("properties") else []
	if p.has("properties") and not include.has("properties"):
		include = include.duplicate()
		include.append("properties")
	var all_editor_properties: bool = include.has("properties") and not p.has("properties")
	var budget: Array = [5000, false, false]
	var inherited: SceneState = inherited_state(root)
	var result: Dictionary = {"scene": root.scene_file_path, "unsaved": root.scene_file_path in EditorInterface.get_unsaved_scenes(), "inherited_source": inherited.get_path() if inherited else null, "root": describe(start, root, names, int(p.get("depth", 8)), budget, include, all_editor_properties), "truncated": bool(budget[1]) or bool(budget[2]), "depth_truncated": bool(budget[1]), "budget_truncated": bool(budget[2])}
	return result

func inherited_state(root: Node) -> SceneState:
	# Node's internal inherited state is not exposed to GDScript.
	# Packing the live tree preserves the base SceneState, including unsaved edits.
	var packed := PackedScene.new()
	if packed.pack(root) != OK: return null
	var base: SceneState = packed.get_state().get_base_scene_state()
	if base: return base
	if not root.scene_file_path.is_empty():
		var saved: PackedScene = host.resource_uri(root.scene_file_path) as PackedScene
		if saved: return saved.get_state().get_base_scene_state()
	return null

func describe(node: Node, root: Node, names: Array, depth: int, budget: Array, include: Array = ["properties", "overrides", "connections", "layout"], all_editor_properties: bool = false) -> Dictionary:
	budget[0] -= 1
	var values: Dictionary = {}
	var overrides: Dictionary = {}
	var include_properties: bool = include.has("properties")
	var include_overrides: bool = include.has("overrides")
	for prop: Dictionary in node.get_property_list():
		var name: String = str(prop.name)
		var selected: bool = include_properties and ((all_editor_properties and int(prop.usage) & PROPERTY_USAGE_EDITOR) or name in names)
		var current: Variant = node.get(name)
		if selected:
			values[name] = host.encode(current)
		if include_overrides and node.property_can_revert(name) and current != node.property_get_revert(name):
			overrides[name] = {"value": host.encode(current), "revert_value": host.encode(node.property_get_revert(name))}
	var result: Dictionary = {"ref": {"scene": root.scene_file_path, "path": str(root.get_path_to(node))}, "name": str(node.name), "class": node.get_class(), "script": host.encode(node.get_script()), "instance_source": node.scene_file_path if node != root else null, "owner": str(root.get_path_to(node.owner)) if node.owner else null, "children": []}
	if include_properties:
		result.properties = values
	if include_overrides:
		result.overrides = overrides
	if include.has("connections"):
		result.connections = connections(node, root)
	if include.has("layout") and node is Control:
		result.layout = {"rect": host.encode(node.get_rect()), "global_rect": host.encode(node.get_global_rect()), "parent_class": node.get_parent().get_class() if node.get_parent() else null, "container_managed": node.get_parent() is Container, "minimum_size": host.encode(node.get_combined_minimum_size()), "anchors": [node.anchor_left, node.anchor_top, node.anchor_right, node.anchor_bottom], "size_flags": {"horizontal": node.size_flags_horizontal, "vertical": node.size_flags_vertical}}
	if depth > 0:
		for child: Node in node.get_children():
			if budget[0] <= 0:
				if budget.size() > 2: budget[2] = true
				break
			result.children.append(describe(child, root, names, depth - 1, budget, include, all_editor_properties))
	else:
		if not node.get_children().is_empty() and budget.size() > 1: budget[1] = true
	return result

func connections(node: Node, root: Node) -> Array:
	var results: Array = []
	for sig: Dictionary in node.get_signal_list():
		for connection: Dictionary in node.get_signal_connection_list(sig.name):
			var target: Object = connection.callable.get_object()
			if int(connection.flags) & CONNECT_PERSIST:
				results.append({"from": host.node_ref(node), "signal": str(sig.name), "to": host.node_ref(target) if target is Node and (target == root or root.is_ancestor_of(target)) else host.encode(target), "method": str(connection.callable.get_method()), "binds": host.encode(connection.callable.get_bound_arguments())})
	return results

func affected_references(root: Node, targets: Array[Node]) -> Array:
	var found: Array = []
	var pending: Array[Node] = [root]
	while not pending.is_empty():
		var node: Node = pending.pop_back()
		for child: Node in node.get_children(): pending.append(child)
		for sig: Dictionary in node.get_signal_list():
			for connection: Dictionary in node.get_signal_connection_list(sig.name):
				if not int(connection.flags) & CONNECT_PERSIST: continue
				var receiver: Object = connection.callable.get_object()
				for target: Node in targets:
					if node == target or target.is_ancestor_of(node) or receiver == target or (receiver is Node and target.is_ancestor_of(receiver)):
						found.append({"kind": "signal", "from": host.node_ref(node), "signal": str(sig.name), "to": host.node_ref(receiver) if receiver is Node else null, "method": str(connection.callable.get_method())})
						break
		for prop: Dictionary in node.get_property_list():
			if int(prop.type) != TYPE_NODE_PATH: continue
			var path: NodePath = node.get(prop.name)
			var receiver: Node = node.get_node_or_null(NodePath(str(path).get_slice(":", 0))) if not path.is_empty() else null
			for target: Node in targets:
				if receiver and (receiver == target or target.is_ancestor_of(receiver)):
					found.append({"kind": "node_path", "node": host.node_ref(node), "property": str(prop.name), "value": str(path), "target": host.node_ref(receiver)})
	return found

func create_scene(p: Dictionary) -> Dictionary:
	var uri: String = p.get("uri", "")
	if not uri.begins_with("res://") or not uri.ends_with(".tscn"): return host.fail("INVALID_PATH", "Scene path must be res://...tscn.")
	if FileAccess.file_exists(uri): return host.fail("ALREADY_EXISTS", "Scene already exists.")
	var name: String = p.get("root_name", "Root")
	if name != name.validate_node_name() or name.is_empty(): return host.fail("INVALID_NAME", "Root name contains invalid characters.")
	var root: Node
	if p.has("inherits"):
		var packed: PackedScene = host.resource_uri(str(p.inherits)) as PackedScene
		if not packed: return host.fail("SCENE_NOT_FOUND", "Inherited source is not a PackedScene.")
		# Serialize an explicit base instance: instantiate/pack alone flattens inheritance.
		DirAccess.make_dir_recursive_absolute(uri.get_base_dir())
		var inherited_file := FileAccess.open(uri, FileAccess.WRITE)
		if not inherited_file: return host.fail("SAVE_FAILED", error_string(FileAccess.get_open_error()))
		inherited_file.store_string('[gd_scene load_steps=2 format=3]\n\n[ext_resource type="PackedScene" path=%s id="1"]\n\n[node name=%s instance=ExtResource("1")]\n' % [JSON.stringify(str(p.inherits)), JSON.stringify(name)])
		inherited_file.close()
		EditorInterface.get_resource_filesystem().update_file(uri)
		EditorInterface.open_scene_from_path(uri)
		await host.get_tree().process_frame
		return {"scene": uri, "root": {"scene": uri, "path": "."}, "saved": true, "inherits": p.inherits}
	else:
		var cls: String = p.get("root_class", "Node")
		if not ClassDB.can_instantiate(cls) or not ClassDB.is_parent_class(cls, "Node"): return host.fail("INVALID_CLASS", "Root must be an instantiable Node.")
		root = ClassDB.instantiate(cls) as Node
	root.name = name
	var scene := PackedScene.new()
	var error: Error = scene.pack(root)
	if error == OK:
		error = DirAccess.make_dir_recursive_absolute(uri.get_base_dir())
	if error == OK:
		error = ResourceSaver.save(scene, uri)
	root.free()
	if error != OK: return host.fail("SAVE_FAILED", error_string(error))
	EditorInterface.get_resource_filesystem().update_file(uri)
	EditorInterface.open_scene_from_path(uri)
	await host.get_tree().process_frame
	return {"scene": uri, "root": {"scene": uri, "path": "."}, "saved": true, "undo_scope": "New document creation is a filesystem operation; subsequent node edits use editor undo."}

func build_node(spec: Dictionary, budget: Array[int]) -> Dictionary:
	budget[0] -= 1
	if budget[0] < 0: return host.fail("LIMIT_EXCEEDED", "A subtree may contain at most 1000 nodes.")
	var name: String = spec.get("name", "Node")
	if name.is_empty() or name != name.validate_node_name(): return host.fail("INVALID_NAME", "Node name contains invalid characters.")
	var selected: Variant = spec.get("source")
	if not selected is Dictionary or selected.size() != 1:
		return host.fail("INVALID_ARGUMENT", "source must select exactly one class, instance, or duplicate.")
	var node: Node
	if selected.has("instance") and selected.instance is String:
		var source: PackedScene = host.resource_uri(selected.instance) as PackedScene
		if source: node = source.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
	elif selected.has("duplicate") and selected.duplicate is Dictionary:
		var source: Node = host.resolve_node(selected.duplicate)
		if source: node = source.duplicate()
	elif selected.has("class") and selected["class"] is String:
		var cls: String = selected["class"]
		if ClassDB.can_instantiate(cls) and ClassDB.is_parent_class(cls, "Node"):
			node = ClassDB.instantiate(cls) as Node
	if not node: return host.fail("INVALID_NODE", "Node type or instance/duplicate source cannot be constructed.")
	node.name = name
	var values: Dictionary = spec.get("properties", {})
	var property_plan: Dictionary = host.plan_property_changes(node, values)
	if property_plan.has("error"):
		node.free()
		return property_plan
	for change: Dictionary in property_plan.get("changes", []): node.set(change.property, change.after)
	return {"node": node}

func set_owner(node: Node, root: Node) -> void:
	node.owner = root
	for child: Node in node.get_children():
		if child.owner == null: set_owner(child, root)

func add_node(parent: Node, node: Node, root: Node) -> void:
	parent.add_child(node, true)
	set_owner(node, root)

func create_nodes(p: Dictionary) -> Dictionary:
	var parent: Node = host.resolve_node(p.get("parent", {}))
	if not parent: return host.fail("NODE_NOT_FOUND", "Parent does not exist.")
	var root: Node = host.scene_root(str(p.parent.scene))
	if parent != root and parent.owner != root:
		return host.fail("INHERITED_NODE", "Add structure in the source scene rather than inside an uneditable instance.")
	var specs: Array = p.get("nodes", [])
	if specs.is_empty(): return host.fail("EMPTY_EDIT", "Provide nodes to create.")
	var key_indices: Dictionary = {}
	for i: int in specs.size():
		var spec: Dictionary = specs[i]
		if spec.has("children"):
			return host.fail("NESTED_CHILDREN_UNSUPPORTED", "Use flat nodes with parent_key; nested children are not supported.")
		if spec.has("key"):
			var key: String = str(spec.key)
			if key.is_empty(): return host.fail("INVALID_KEY", "Node key must be non-empty when provided.")
			if key_indices.has(key): return host.fail("DUPLICATE_KEY", "Each node key must be unique: %s." % key)
			key_indices[key] = i
	for spec: Dictionary in specs:
		if spec.has("parent_key"):
			var parent_key: String = str(spec.parent_key)
			if parent_key.is_empty() or not key_indices.has(parent_key):
				return host.fail("UNKNOWN_PARENT_KEY", "parent_key must reference a node key in this batch.")
	var parent_by_key: Dictionary = {}
	for spec: Dictionary in specs:
		if spec.has("key") and spec.has("parent_key"):
			parent_by_key[str(spec.key)] = str(spec.parent_key)
	for key: String in parent_by_key:
		var seen: Dictionary = {}
		var cursor: String = key
		while parent_by_key.has(cursor):
			if seen.has(cursor): return host.fail("PARENT_CYCLE", "parent_key relationships must not contain cycles.")
			seen[cursor] = true
			cursor = parent_by_key[cursor]
	var nodes: Array[Node] = []
	var budget: Array[int] = [1000]
	for spec: Dictionary in specs:
		var result: Dictionary = build_node(spec, budget)
		if result.has("error"):
			for node: Node in nodes: node.free()
			return result
		nodes.append(result.node)
	var keyed_nodes: Dictionary = {}
	for i: int in specs.size():
		if specs[i].has("key"): keyed_nodes[str(specs[i].key)] = nodes[i]
	var top_level: Array[Node] = []
	for i: int in specs.size():
		var spec: Dictionary = specs[i]
		if spec.has("parent_key"):
			keyed_nodes[str(spec.parent_key)].add_child(nodes[i], true)
		else:
			top_level.append(nodes[i])
	host.begin_edit("Create nodes", root)
	var undo: EditorUndoRedoManager = host.get_undo_redo()
	for node: Node in top_level:
		undo.add_do_method(self, "add_node", parent, node, root)
		undo.add_undo_method(parent, "remove_child", node)
		undo.add_do_reference(node)
	var result: Dictionary = host.finish_edit(root, "Create nodes")
	await host.get_tree().process_frame
	result.nodes = []
	for i: int in nodes.size():
		result.nodes.append({"key": specs[i].get("key", ""), "ref": host.node_ref(nodes[i])})
	return result

func structural_error(node: Node, root: Node) -> String:
	if node == root: return "Scene roots cannot be reparented or removed."
	if node.owner != root: return "This child belongs to an instanced scene; edit its source."
	var inherited: SceneState = inherited_state(root)
	while inherited:
		for i: int in inherited.get_node_count():
			if str(inherited.get_node_path(i)).trim_prefix("./") == str(root.get_path_to(node)).trim_prefix("./"): return "This node is inherited; edit its source scene."
		inherited = inherited.get_base_scene_state()
	return ""

func reparent_node(node: Node, parent: Node, index: int, owner: Node, keep_global: bool, transform: Variant = null) -> void:
	if node.get_parent(): node.reparent(parent, keep_global)
	else: parent.add_child(node, true)
	parent.move_child(node, clampi(index, 0, parent.get_child_count() - 1))
	set_owner(node, owner)
	if transform != null:
		if node is Node2D or node is Node3D: node.transform = transform
		elif node is Control:
			node.position = transform.position
			node.size = transform.size

func update_nodes(p: Dictionary) -> Dictionary:
	var staged: Array[Dictionary] = []
	var targets: Array[Node] = []
	var root: Node
	for change: Dictionary in p.get("changes", []):
		var node: Node = host.resolve_node(change.get("node", {}))
		if not node: return host.fail("NODE_NOT_FOUND", "An update target does not exist.")
		var scene: Node = host.scene_root(change.node.scene)
		if root and root != scene: return host.fail("CROSS_SCENE", "Batch updates must belong to one scene document.")
		root = scene
		if node in targets: return host.fail("DUPLICATE_TARGET", "Combine changes to the same node in one entry.")
		var values: Dictionary = change.get("set", {})
		if node.get_parent() is Container and (values.has("position") or values.has("size")):
			return host.fail("CONTAINER_LAYOUT", "Parent Container determines position and size. Edit size flags/minimum sizes or the parent settings.")
		var property_plan: Dictionary = host.plan_property_changes(node, values)
		if property_plan.has("error"): return property_plan
		if change.has("name") and (str(change.name).is_empty() or str(change.name) != str(change.name).validate_node_name()): return host.fail("INVALID_NAME", "Invalid node name.")
		if (change.has("parent") or change.has("name")) and node != root:
			var structural: String = structural_error(node, root)
			if not structural.is_empty(): return host.fail("INHERITED_NODE", structural)
		var parent: Node = node.get_parent()
		if change.has("parent"):
			parent = host.resolve_node(change.parent)
			if not parent or change.parent.scene != change.node.scene or node == root or parent == node or node.is_ancestor_of(parent): return host.fail("INVALID_PARENT", "New parent is missing, outside the document or creates a cycle.")
		if change.has("name") and parent:
			var sibling: Node = parent.get_node_or_null(NodePath(str(change.name)))
			if sibling and sibling != node: return host.fail("NAME_CONFLICT", "A sibling already has this name.")
		staged.append({"node": node, "change": change, "property_plan": property_plan, "parent": parent, "old_parent": node.get_parent(), "old_index": node.get_index(), "old_owner": node.owner})
		targets.append(node)
	if staged.is_empty(): return host.fail("EMPTY_EDIT", "Provide changes.")
	# Combined reparent operations can form a cycle even when each is valid alone.
	for item: Dictionary in staged:
		var chain: Array[Node] = [item.node]
		var parent: Node = item.parent
		while parent and parent != root:
			if parent in chain: return host.fail("INVALID_PARENT", "The batch creates a parent cycle.")
			chain.append(parent)
			var next: Node = parent.get_parent()
			for other: Dictionary in staged:
				if other.node == parent: next = other.parent
			parent = next
	var affected: Array = affected_references(root, targets)
	host.begin_edit("Update nodes", root)
	var undo: EditorUndoRedoManager = host.get_undo_redo()
	for item: Dictionary in staged:
		var node: Node = item.node
		var change: Dictionary = item.change
		if node.owner and node.owner != root and not root.is_editable_instance(node.owner):
			undo.add_do_method(root, "set_editable_instance", node.owner, true)
			undo.add_undo_method(root, "set_editable_instance", node.owner, false)
		host.add_changes(item.property_plan.get("changes", []))
		if change.has("name"):
			undo.add_do_property(node, "name", StringName(change.name))
			undo.add_undo_property(node, "name", node.name)
		if change.has("parent") or change.has("index"):
			var transform: Variant = node.transform if node is Node2D or node is Node3D else ({"position": node.position, "size": node.size} if node is Control else null)
			undo.add_do_method(self, "reparent_node", node, item.parent, int(change.get("index", item.parent.get_child_count())), root, bool(change.get("keep_global_transform", true)))
			undo.add_undo_method(self, "reparent_node", node, item.old_parent, item.old_index, item.old_owner, false, transform)
	var result: Dictionary = host.finish_edit(root, "Update nodes")
	await host.get_tree().process_frame
	result.nodes = []
	for item: Dictionary in staged:
		var budget: Array[int] = [1]
		result.nodes.append(describe(item.node, root, item.change.get("set", {}).keys(), 0, budget))
	result.affected_references = affected
	result.reference_note = "Persistent signals follow node objects. Review NodePath/script/animation references after structural changes."
	return result

func delete_nodes(p: Dictionary) -> Dictionary:
	var nodes: Array[Node] = []
	var root: Node
	for ref: Dictionary in p.get("nodes", []):
		var node: Node = host.resolve_node(ref)
		if not node: return host.fail("NODE_NOT_FOUND", "A deletion target does not exist.")
		var scene: Node = host.scene_root(ref.scene)
		if root and root != scene: return host.fail("CROSS_SCENE", "Delete nodes from one scene per batch.")
		root = scene
		var error: String = structural_error(node, root)
		if not error.is_empty(): return host.fail("INHERITED_NODE", error)
		for other: Node in nodes:
			if node == other or node.is_ancestor_of(other) or other.is_ancestor_of(node): return host.fail("OVERLAPPING_SELECTION", "Select each subtree once.")
		nodes.append(node)
	if nodes.is_empty(): return host.fail("EMPTY_EDIT", "Provide nodes to delete.")
	var affected: Array = affected_references(root, nodes)
	var refs: Array = []
	host.begin_edit("Delete nodes", root)
	var undo: EditorUndoRedoManager = host.get_undo_redo()
	for node: Node in nodes:
		refs.append(host.node_ref(node))
		undo.add_do_method(node.get_parent(), "remove_child", node)
		undo.add_undo_method(self, "reparent_node", node, node.get_parent(), node.get_index(), node.owner, false)
		undo.add_undo_reference(node)
	var result: Dictionary = host.finish_edit(root, "Delete nodes")
	await host.get_tree().process_frame
	result.deleted = refs
	result.affected_references = affected
	return result
