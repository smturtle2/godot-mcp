extends RefCounted
## Operation owners report effects and unfinished stages; transport reads this outcome.

static func finish(result: Dictionary, applied: bool, failures: Array = [], pending: Array = []) -> Dictionary:
	var complete: bool = failures.is_empty() and pending.is_empty()
	result.status = "completed" if complete else ("partial" if applied else "failed")
	result.complete = complete
	result.failures = failures
	result.pending = pending
	return result

static func failure(phase: String, error: Dictionary) -> Dictionary:
	return {"phase": phase, "code": str(error.get("code", "OPERATION_FAILED")), "message": str(error.get("message", "The requested stage failed.")), "details": error.get("details", {})}
