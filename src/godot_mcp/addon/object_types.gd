@tool
extends RefCounted
## Native classes and authored script types have different identities.

static func describe(value: Object) -> Dictionary:
	var script: Script = value.get_script() as Script
	return {"class": value.get_class(), "resource": value.resource_path if value is Resource else "", "script": script.resource_path if script else "", "script_class": script.get_global_name() if script else ""}

static func check(value: Object, expected: String) -> Dictionary:
	if expected.is_empty(): return {}
	var details: Dictionary = {"expected": expected, "actual": describe(value)}
	if ClassDB.class_exists(expected):
		if value.is_class(expected): return {}
	else:
		var path: String = expected if expected.begins_with("res://") else ""
		for entry: Dictionary in ProjectSettings.get_global_class_list():
			if entry["class"] == expected:
				path = entry.path
				break
		details.expected_script = path
		var required: Script = load(path) as Script if not path.is_empty() and ResourceLoader.exists(path) else null
		if not required:
			return {"code": "TYPE_UNAVAILABLE", "message": "Cannot resolve the declared script type: " + expected, "details": details}
		var script: Script = value.get_script() as Script
		while script:
			if script == required: return {}
			script = script.get_base_script()
	return {"code": "TYPE_MISMATCH", "message": "Expected " + expected + "; the supplied object's native class or script ancestry differs.", "details": details}
