@tool
extends RefCounted
## Native classes and authored script types have different identities.

static func describe(value: Object) -> Dictionary:
	var script: Script = value.get_script() as Script
	return {"class": value.get_class(), "resource": value.resource_path if value is Resource else "", "script": script.resource_path if script else "", "script_class": script.get_global_name() if script else ""}

static func check(value: Object, expected: String) -> Dictionary:
	if expected.is_empty(): return {}
	var details: Dictionary = {"expected": expected, "actual": describe(value)}
	var candidates: Array[String] = []
	for raw_candidate: String in expected.split(","):
		var candidate: String = raw_candidate.strip_edges()
		if not candidate.is_empty(): candidates.append(candidate)
	details.candidates = candidates
	var unavailable: Array[String] = []
	for candidate: String in candidates:
		if ClassDB.class_exists(candidate):
			if value.is_class(candidate): return {}
			continue
		var path: String = candidate if candidate.begins_with("res://") else ""
		for entry: Dictionary in ProjectSettings.get_global_class_list():
			if entry["class"] == candidate:
				path = entry.path
				break
		if candidates.size() == 1: details.expected_script = path
		var required: Script = load(path) as Script if not path.is_empty() and ResourceLoader.exists(path) else null
		if not required:
			unavailable.append(candidate)
			continue
		var script: Script = value.get_script() as Script
		while script:
			if script == required: return {}
			script = script.get_base_script()
	if not unavailable.is_empty():
		details.unavailable = unavailable
		var unavailable_text: String = ", ".join(unavailable)
		var message: String = "Cannot resolve the declared type alternative(s): " + unavailable_text
		if candidates.size() == 1: message = "Cannot resolve the declared script type: " + expected
		return {"code": "TYPE_UNAVAILABLE", "message": message, "details": details}
	return {"code": "TYPE_MISMATCH", "message": "Expected " + expected + "; the supplied object's native class or script ancestry differs.", "details": details}
