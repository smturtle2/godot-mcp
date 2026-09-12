@tool
extends RefCounted
const ObjectTypes = preload("res://addons/godot_mcp/object_types.gd")
## Shared property inspection and validation for editor mutations.
var host: EditorPlugin

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func info(object: Object, property: String) -> Dictionary:
	if not object:
		return {}
	for entry: Dictionary in object.get_property_list():
		if str(entry.get("name", "")) == property:
			return entry
	return {}

func _error(message: String, property: String = "") -> Dictionary:
	return host.fail("INVALID_PROPERTY", message, {"property": property})

func plan(object: Object, values: Dictionary, parent_context: Node = null) -> Dictionary:
	if not object:
		return _error("Property target does not exist.")
	var changes: Array[Dictionary] = []
	for key: String in values:
		var property_info: Dictionary = info(object, key)
		if property_info.is_empty():
			return _error("Unknown property: " + key, key)
		if object is Control:
			var parent: Node = parent_context if parent_context else object.get_parent()
			if parent is Container and key in ["layout_mode", "position", "size", "rotation", "scale", "anchor_left", "anchor_right", "anchor_top", "anchor_bottom", "offset_left", "offset_right", "offset_top", "offset_bottom", "anchors_preset"]:
				return host.fail("CONTAINER_LAYOUT", "Parent Container manages this layout; use size flags, custom_minimum_size or the parent settings.", {"property": key, "parent_class": parent.get_class()})
			# Newly constructed Controls have no live parent yet. Godot marks
			# layout_mode read-only in that state, even under a planned Control.
			if key == "layout_mode" and parent_context is Control and not parent_context is Container:
				property_info.usage = int(property_info.usage) & ~PROPERTY_USAGE_READ_ONLY
		if int(property_info.get("usage", 0)) & PROPERTY_USAGE_READ_ONLY:
			return _error("Read-only property: " + key, key)
		# Decode exactly once so validation and the resulting change use the same value.
		var encoded: Variant = values[key]
		var value: Variant
		if encoded is Dictionary and encoded.get("$type") == "Resource" and encoded.has("class"):
			var cls: String = str(encoded["class"])
			if encoded.has("uri") or not ClassDB.can_instantiate(cls) or not ClassDB.is_parent_class(cls, "Resource") or ClassDB.is_parent_class(cls, "Script"):
				return _error("Inline resource requires an instantiable engine Resource class and no uri.", key)
			value = ClassDB.instantiate(cls)
			var nested: Dictionary = plan(value, encoded.get("properties", {}))
			if nested.has("error"):
				nested.error.details.property = key + "." + str(nested.error.details.get("property", ""))
				return nested
			for item: Dictionary in nested.changes: value.set(item.property, item.after)
		else:
			value = host.decode(encoded)
		if encoded is Dictionary and encoded.get("$type") == "Resource" and value == null:
			return _error("Resource reference does not exist: " + str(encoded.get("uri", "")), key)
		var expected: int = int(property_info.get("type", TYPE_NIL))
		if value == null:
			if expected not in [TYPE_NIL, TYPE_OBJECT]:
				return _error("Null is not valid for " + key, key)
		elif expected != TYPE_NIL and typeof(value) != expected:
			var coercible: bool = (expected == TYPE_FLOAT and value is int) or (expected == TYPE_INT and value is float and float(int(value)) == value) or (expected == TYPE_STRING_NAME and value is String)
			if not coercible:
				return _error("Wrong type for %s: expected %s" % [key, type_string(expected)], key)
		if expected == TYPE_INT and value is float:
			value = int(value)
		elif expected == TYPE_STRING_NAME and value is String:
			value = StringName(value)
		if expected == TYPE_OBJECT and value != null:
			var expected_class := str(property_info.get("class_name", ""))
			var mismatch: Dictionary = ObjectTypes.check(value, expected_class)
			if not mismatch.is_empty():
				mismatch.details.property = key
				return {"error": mismatch}
		if object is Node and key == "script" and value is Script:
			var prepared: Dictionary = host.documents.store.prepare_script(value)
			if prepared.has("error"): return prepared
			var base_type: String = value.get_instance_base_type()
			if base_type.is_empty(): return host.fail("SCRIPT_NOT_READY", "The script's base type is not available yet.", {"uri": value.resource_path})
			if not object.is_class(base_type):
				return host.fail("TYPE_MISMATCH", "The script base type is incompatible with the target node.", {"uri": value.resource_path, "expected": base_type, "actual": object.get_class()})
		changes.append({"object": object, "property": key, "before": object.get(key), "after": value})
	return {"changes": changes}
