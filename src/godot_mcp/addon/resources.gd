@tool
extends RefCounted
var host: EditorPlugin

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func handles(method: String) -> bool:
	return method in ["get_resource", "create_resource", "update_resource"]

func dispatch(method: String, p: Dictionary) -> Dictionary:
	match method:
		"get_resource":
			var target: Dictionary = host.resolve_resource_target(p.get("target", {}))
			if target.has("error"): return target
			return describe(target.resource, p.get("properties", []), int(p.get("depth", 1)))
		"create_resource": return create_resource(p)
		"update_resource": return update_resource(p)
	return host.fail("UNKNOWN_TOOL", method)

func imported(resource: Resource) -> bool:
	return host.documents.resource_storage(resource) == "imported"

func nested(value: Variant, wanted: Resource, seen: Dictionary, depth: int = 0) -> bool:
	if value is Resource and value == wanted: return true
	if depth > 8: return false
	if value is Resource:
		var id: int = value.get_instance_id()
		if seen.has(id): return false
		seen[id] = true
		for prop: Dictionary in value.get_property_list():
			if int(prop.usage) & PROPERTY_USAGE_STORAGE and nested(value.get(prop.name), wanted, seen, depth + 1): return true
	elif value is Array:
		for item: Variant in value:
			if nested(item, wanted, seen, depth + 1): return true
	elif value is Dictionary:
		for item: Variant in value.values():
			if nested(item, wanted, seen, depth + 1): return true
	return false

func users(resource: Resource) -> Dictionary:
	var open_users: Array = []
	for root: Node in EditorInterface.get_open_scene_roots():
		var pending: Array[Node] = [root]
		while not pending.is_empty():
			var node: Node = pending.pop_back()
			for child: Node in node.get_children(): pending.append(child)
			for prop: Dictionary in node.get_property_list():
				if not int(prop.usage) & PROPERTY_USAGE_STORAGE: continue
				if nested(node.get(prop.name), resource, {}):
					open_users.append({"node": host.node_ref(node), "property": str(prop.name), "direct": node.get(prop.name) == resource})
	var dependencies: Array = []
	var path: String = resource.resource_path.get_slice("::", 0)
	if not path.is_empty():
		var dirs: Array[EditorFileSystemDirectory] = [EditorInterface.get_resource_filesystem().get_filesystem()]
		var count: int = 0
		while not dirs.is_empty() and count < 20000:
			var dir: EditorFileSystemDirectory = dirs.pop_back()
			for i: int in dir.get_subdir_count(): dirs.append(dir.get_subdir(i))
			for i: int in dir.get_file_count():
				count += 1
				for dep: String in ResourceLoader.get_dependencies(dir.get_file_path(i)):
					if host.assets.dependencies.resolve(dep) == path:
						dependencies.append(dir.get_file_path(i))
						break
	return {"open_scene_users": open_users, "indexed_dependencies": dependencies, "scope": "open scene object identity and indexed serialized dependencies; dynamic code references are not enumerable"}

func describe(resource: Resource, names: Array = [], depth: int = 1, seen: Dictionary = {}) -> Dictionary:
	var uri: String = host.register_resource(resource)
	var result: Dictionary = {"resource": host.encode(resource), "uri": uri, "class": resource.get_class(), "local_to_scene": resource.resource_local_to_scene, "imported": imported(resource), "properties": {}, "nested": [], "sharing": users(resource)}
	seen[resource.get_instance_id()] = true
	for prop: Dictionary in resource.get_property_list():
		var name: String = str(prop.name)
		if (names.is_empty() and int(prop.usage) & PROPERTY_USAGE_EDITOR) or name in names:
			var value: Variant = resource.get(name)
			result.properties[name] = host.encode(value)
			if depth > 0 and value is Resource and not seen.has(value.get_instance_id()):
				result.nested.append({"property": name, "value": describe(value, [], depth - 1, seen)})
	return result

func save_new(resource: Resource, uri: String) -> Error:
	if not uri.begins_with("res://") or uri.get_extension() not in ["tres", "res"]: return ERR_INVALID_PARAMETER
	if FileAccess.file_exists(uri): return ERR_ALREADY_EXISTS
	var error: Error = DirAccess.make_dir_recursive_absolute(uri.get_base_dir())
	if error != OK: return error
	error = ResourceSaver.save(resource, uri, ResourceSaver.FLAG_CHANGE_PATH)
	if error == OK:
		# The saved path resolves to this editor object, including later calls
		# that previously received its still-valid in-memory alias.
		resource.take_over_path(uri)
		EditorInterface.get_resource_filesystem().update_file(uri)
		host.register_resource(resource)
	return error

func create_resource(p: Dictionary) -> Dictionary:
	var cls: String = p.get("class", "Resource")
	if not ClassDB.can_instantiate(cls) or not ClassDB.is_parent_class(cls, "Resource") or ClassDB.is_parent_class(cls, "Script"):
		return host.fail("INVALID_CLASS", "Use an instantiable Resource class; use apply_script_changes for code.")
	var resource: Resource = ClassDB.instantiate(cls) as Resource
	var property_plan: Dictionary = host.plan_property_changes(resource, p.get("properties", {}))
	if property_plan.has("error"): return property_plan
	for change: Dictionary in property_plan.get("changes", []): resource.set(change.property, change.after)
	var uri: String = host.register_resource(resource)
	var node: Node
	var property: String
	if p.has("assign_to"):
		node = host.resolve_node(p.assign_to.get("node", {}))
		property = p.assign_to.get("property", "")
		if not node: return host.fail("NODE_NOT_FOUND", "Assignment target does not exist.")
		var assignment_plan: Dictionary = host.plan_property_changes(node, {property: {"$type": "Resource", "uri": uri}})
		if assignment_plan.has("error"): return assignment_plan
	if p.has("save_as"):
		var saved: Error = save_new(resource, p.save_as)
		if saved != OK: return host.fail("SAVE_FAILED", error_string(saved))
	var result: Dictionary = {"resource": host.encode(resource), "saved": p.has("save_as")}
	if node:
		result.merge(host.commit_changes([{"object": node, "property": property, "before": node.get(property), "after": resource}], host.scene_root(p.assign_to.node.scene), "Assign resource"), true)
		result.assigned_to = p.assign_to
		result.resource_saved = p.has("save_as")
	return result

func update_resource(p: Dictionary) -> Dictionary:
	var target: Dictionary = host.resolve_scoped_resource_target(p.get("target", {}))
	if target.has("error"): return target
	var scope: String = target.scope
	var resource: Resource = target.resource
	if scope == "shared" and imported(resource): return host.fail("IMPORTED_RESOURCE", "Detach imported resources with local scope, optionally saving as an authored .tres file.")
	var property_plan: Dictionary = host.plan_property_changes(resource, p.get("set", {}))
	if property_plan.has("error"): return property_plan
	var before_users: Dictionary = users(resource)
	var result: Dictionary
	if scope == "local":
		var node: Node = target.node
		var replacement: Resource = resource.duplicate(true)
		replacement.resource_local_to_scene = true
		for change: Dictionary in property_plan.get("changes", []): replacement.set(change.property, change.after)
		if p.has("save_as"):
			var saved: Error = save_new(replacement, p.save_as)
			if saved != OK: return host.fail("SAVE_FAILED", error_string(saved))
		result = host.commit_changes([{"object": node, "property": target.property, "before": resource, "after": replacement}], host.scene_root(target.scene), "Isolate resource")
		resource = replacement
		result.affected = [target.reference]
	else:
		if p.has("save_as"): return host.fail("INVALID_ARGUMENT", "Use save_documents to save a shared resource under a new path.")
		result = host.commit_changes(property_plan.get("changes", []), resource, "Update shared resource")
		result.affected = before_users
	result.scope = scope
	result.resource = host.encode(resource)
	result.properties = {}
	for key: String in p.get("set", {}): result.properties[key] = host.encode(resource.get(key))
	result.reimport_persistence = "authored copy; save its scene/resource" if scope == "local" else "authored shared resource; save explicitly"
	return result
