@tool
extends RefCounted

var host: EditorPlugin

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func resolve(selector: Dictionary, scope: String = "", expected_class: String = "Resource") -> Dictionary:
	if not selector is Dictionary:
		return host.fail("INVALID_TARGET", "Target must be a resource selector.")
	if scope not in ["", "node", "shared"]:
		return host.fail("INVALID_SCOPE", "Scope must be node, shared, or omitted.")
	var keys: Array = selector.keys()
	if selector.has("uri"):
		if scope == "node":
			return host.fail("SCOPE_REQUIRED", "Node scope requires a node property target.")
		if keys.size() != 1 or not selector.uri is String or str(selector.uri).is_empty():
			return host.fail("INVALID_TARGET", "URI targets must contain exactly one non-empty uri.")
		var resource: Resource = host.resource_uri(str(selector.uri))
		return _resource_result(resource, expected_class, scope, {}, {"uri": str(selector.uri)})
	if not selector.has("node") or not selector.has("property") or keys.size() != 2:
		return host.fail("INVALID_TARGET", "Use exactly {uri} or {node:{scene,path},property}.")
	if not selector.node is Dictionary:
		return host.fail("INVALID_TARGET", "Node target must contain a node object.")
	var node_ref: Dictionary = selector.node
	if node_ref.keys().size() != 2 or not node_ref.has("scene") or not node_ref.has("path"):
		return host.fail("INVALID_TARGET", "Node targets require exactly scene and path.")
	if not node_ref.scene is String or not node_ref.path is String or str(node_ref.scene).is_empty() or str(node_ref.path).is_empty():
		return host.fail("INVALID_TARGET", "Node target scene and path must be non-empty strings.")
	if not selector.property is String or str(selector.property).is_empty():
		return host.fail("INVALID_TARGET", "Node targets require a non-empty property.")
	var node: Node = host.resolve_node(node_ref)
	if not node: return host.fail("NODE_NOT_FOUND", "Target node does not exist.")
	var property: String = str(selector.property)
	if host.property_info(node, property).is_empty(): return host.fail("PROPERTY_NOT_FOUND", "Target property does not exist: " + property)
	var value: Variant = node.get(property)
	if not value is Resource: return host.fail("INVALID_RESOURCE", "Target property does not contain a Resource.")
	return _resource_result(value as Resource, expected_class, scope, {"node": node, "property": property, "scene": str(node_ref.scene)}, {"node": {"scene": str(node_ref.scene), "path": str(node_ref.path)}, "property": property})

func _resource_result(resource: Resource, expected_class: String, scope: String, selected: Dictionary, reference: Dictionary) -> Dictionary:
	if not resource: return host.fail("RESOURCE_NOT_FOUND", "Resource reference is stale or does not exist.")
	if not expected_class.is_empty() and not (resource.get_class() == expected_class or ClassDB.is_parent_class(resource.get_class(), expected_class)):
		return host.fail("INVALID_RESOURCE", "Target resource must be a " + expected_class + ".")
	var result: Dictionary = {"resource": resource, "scope": scope, "reference": reference}
	result.merge(selected)
	return result
