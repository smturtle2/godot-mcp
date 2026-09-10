@tool
extends RefCounted
## Explicit JSON/Variant boundary; never evaluate strings as Godot expressions.

static func encode(value: Variant, register: Callable = Callable(), depth: int = 0) -> Variant:
	if depth > 12:
		return {"truncated": true, "type": type_string(typeof(value))}
	match typeof(value):
		TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING:
			return value
		TYPE_FLOAT:
			return value if is_finite(value) else {"non_finite": str(value)}
		TYPE_STRING_NAME, TYPE_NODE_PATH:
			return {"$type": "StringName" if value is StringName else "NodePath", "value": str(value)}
		TYPE_VECTOR2, TYPE_VECTOR2I:
			return {"$type": type_string(typeof(value)), "x": value.x, "y": value.y}
		TYPE_VECTOR3, TYPE_VECTOR3I:
			return {"$type": type_string(typeof(value)), "x": value.x, "y": value.y, "z": value.z}
		TYPE_VECTOR4, TYPE_VECTOR4I, TYPE_QUATERNION:
			return {"$type": type_string(typeof(value)), "x": value.x, "y": value.y, "z": value.z, "w": value.w}
		TYPE_COLOR:
			return {"$type": "Color", "r": value.r, "g": value.g, "b": value.b, "a": value.a, "space": "linear"}
		TYPE_RECT2, TYPE_RECT2I:
			return {"$type": type_string(typeof(value)), "position": encode(value.position), "size": encode(value.size)}
		TYPE_BASIS:
			return {"$type": "Basis", "x": encode(value.x), "y": encode(value.y), "z": encode(value.z)}
		TYPE_TRANSFORM2D:
			return {"$type": "Transform2D", "x": encode(value.x), "y": encode(value.y), "origin": encode(value.origin)}
		TYPE_TRANSFORM3D:
			return {"$type": "Transform3D", "basis": encode(value.basis), "origin": encode(value.origin)}
		TYPE_OBJECT:
			if not is_instance_valid(value):
				return null
			if value is Resource:
				var uri: String = register.call(value) if register.is_valid() else value.resource_path
				return {"$type": "Resource", "uri": uri, "class": value.get_class()}
			if value is Node:
				return {"$type": "Node", "path": str(value.get_path()) if value.is_inside_tree() else str(value.name), "class": value.get_class()}
			return {"$type": "Object", "class": value.get_class()}
		TYPE_DICTIONARY:
			var out: Dictionary = {}
			for key: Variant in value:
				out[str(key)] = encode(value[key], register, depth + 1)
			return out
		TYPE_ARRAY:
			var out: Array = []
			for item: Variant in value:
				out.append(encode(item, register, depth + 1))
			return out
		TYPE_PACKED_BYTE_ARRAY, TYPE_PACKED_INT32_ARRAY, TYPE_PACKED_INT64_ARRAY, TYPE_PACKED_FLOAT32_ARRAY, TYPE_PACKED_FLOAT64_ARRAY, TYPE_PACKED_STRING_ARRAY, TYPE_PACKED_VECTOR2_ARRAY, TYPE_PACKED_VECTOR3_ARRAY, TYPE_PACKED_VECTOR4_ARRAY, TYPE_PACKED_COLOR_ARRAY:
			var out: Array = []
			for item: Variant in value:
				out.append(encode(item, register, depth + 1))
			return {"$type": type_string(typeof(value)), "values": out}
	return {"$type": type_string(typeof(value)), "display": str(value)}

static func v2(value: Dictionary) -> Vector2:
	return Vector2(float(value.get("x", 0)), float(value.get("y", 0)))

static func v3(value: Dictionary) -> Vector3:
	return Vector3(float(value.get("x", 0)), float(value.get("y", 0)), float(value.get("z", 0)))

static func decode(value: Variant, resolve: Callable = Callable()) -> Variant:
	if value is Array:
		var result: Array = []
		for item: Variant in value:
			result.append(decode(item, resolve))
		return result
	if not value is Dictionary:
		return value
	match str(value.get("$type", "")):
		"Vector2": return v2(value)
		"Vector2i": return Vector2i(v2(value))
		"Vector3": return v3(value)
		"Vector3i": return Vector3i(v3(value))
		"Vector4": return Vector4(value.x, value.y, value.z, value.w)
		"Vector4i": return Vector4i(value.x, value.y, value.z, value.w)
		"Quaternion": return Quaternion(value.x, value.y, value.z, value.w)
		"Color":
			var color := Color(value.r, value.g, value.b, value.a)
			return color.srgb_to_linear() if value.get("space", "linear") == "srgb" else color
		"Rect2": return Rect2(v2(value.position), v2(value.size))
		"Rect2i": return Rect2i(Vector2i(v2(value.position)), Vector2i(v2(value.size)))
		"Basis": return Basis(v3(value.x), v3(value.y), v3(value.z))
		"Transform2D": return Transform2D(v2(value.x), v2(value.y), v2(value.origin))
		"Transform3D":
			var basis: Dictionary = value.basis
			return Transform3D(Basis(v3(basis.x), v3(basis.y), v3(basis.z)), v3(value.origin))
		"NodePath": return NodePath(value.value)
		"StringName": return StringName(value.value)
		"Resource": return resolve.call(value.uri) if resolve.is_valid() else null
		"PackedByteArray": return PackedByteArray(decode(value.values, resolve))
		"PackedInt32Array": return PackedInt32Array(decode(value.values, resolve))
		"PackedInt64Array": return PackedInt64Array(decode(value.values, resolve))
		"PackedFloat32Array": return PackedFloat32Array(decode(value.values, resolve))
		"PackedFloat64Array": return PackedFloat64Array(decode(value.values, resolve))
		"PackedStringArray": return PackedStringArray(decode(value.values, resolve))
		"PackedVector2Array": return PackedVector2Array(decode(value.values, resolve))
		"PackedVector3Array": return PackedVector3Array(decode(value.values, resolve))
		"PackedVector4Array": return PackedVector4Array(decode(value.values, resolve))
		"PackedColorArray": return PackedColorArray(decode(value.values, resolve))
	var result: Dictionary = {}
	for key: Variant in value:
		result[key] = decode(value[key], resolve)
	return result
