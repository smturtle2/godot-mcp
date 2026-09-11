extends RefCounted
## One current record per URI; operation failures and editor undo have one owner.
const OperationResult = preload("res://addons/godot_mcp/operation_result.gd")

static func begin(undo: Dictionary = {}) -> Dictionary:
	return {"documents": [], "failures": [], "pending_save": [], "undo": undo}

static func document(state: Dictionary, effect: String = "") -> Dictionary:
	var record: Dictionary = state.duplicate(true)
	record.erase("saved")
	if not effect.is_empty(): record.effect = effect
	return record

static func put(result: Dictionary, record: Dictionary) -> Dictionary:
	for existing: Dictionary in result.documents:
		if existing.uri != record.uri: continue
		var effect: String = existing.get("effect", "")
		var attempts: Array = []
		if existing.has("save") and record.has("save"):
			attempts.append_array(existing.save.get("attempts", [existing.save.duplicate(true)]))
			attempts.append_array(record.save.get("attempts", [record.save.duplicate(true)]))
		existing.merge(record, true)
		if attempts.size() > 1:
			attempts.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.get("index", -1)) < int(b.get("index", -1)))
			existing.save = attempts[-1].duplicate(true)
			existing.save.attempts = attempts
		if effect in ["created", "updated"]: existing.effect = effect
		return existing
	result.documents.append(record)
	return record

static func validation(record: Dictionary, source: Dictionary) -> void:
	var checked: Dictionary = source.duplicate(true)
	checked.erase("uri")
	checked.erase("valid")
	if checked.get("revision") == record.get("revision"):
		checked.erase("revision")
	elif checked.get("state") in ["valid", "invalid"]:
		# Preserve the snapshot identity instead of binding an old verdict to the
		# current document merely because its URI stayed the same.
		checked.checked_state = checked.state
		checked.state = "pending"
	for entry: Dictionary in checked.get("entries", []):
		if entry.get("uri", "") == record.uri: entry.erase("uri")
	record.validation = checked

static func failure(result: Dictionary, phase: String, code: String, message: String, target: Dictionary = {}, recovery: Dictionary = {}, details: Dictionary = {}) -> void:
	var item: Dictionary = {"phase": phase, "code": code, "message": message}
	item.merge(target)
	if not recovery.is_empty(): item.recovery = recovery
	if not details.is_empty(): item.details = details
	result.failures.append(item)

static func validation_failures(result: Dictionary) -> void:
	for record: Dictionary in result.documents:
		if not record.has("validation"): continue
		var state: String = record.validation.get("state", "unavailable")
		if state == "valid": continue
		var code: String = {"invalid": "SOURCE_INVALID", "pending": "VALIDATION_PENDING"}.get(state, "VALIDATION_UNAVAILABLE")
		failure(result, "validation", code, "Inspect the document validation result before continuing.", {"uri": record.uri},
			{"tool": "get_diagnostics", "arguments": {"uris": [record.uri]}, "prerequisite": "Repair invalid source before expecting validation to pass."} if state == "invalid" else
			{"tool": "get_diagnostics", "arguments": {"uris": [record.uri]}})

static func finish(result: Dictionary, applied: bool) -> Dictionary:
	var pending: Array = []
	for uri: String in result.pending_save:
		if uri not in pending: pending.append(uri)
	for record: Dictionary in result.documents:
		var save_state: String = record.get("save", {}).get("state", "")
		if record.get("state") in ["modified", "draft"] or save_state in ["failed", "skipped"]:
			if record.uri not in pending: pending.append(record.uri)
		elif save_state == "saved":
			# A later successful attempt satisfies the current persistence need;
			# earlier failed attempts still remain in the operation failures.
			pending.erase(record.uri)
	result.pending_save = pending
	OperationResult.finish(result, applied, result.failures)
	return result
