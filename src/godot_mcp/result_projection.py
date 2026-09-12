"""The small mutation receipt; canonical operation snapshots stay in Godot."""
from __future__ import annotations

import copy
from typing import Any

from .catalog import DOCUMENT_TOOLS


def _pick(value: dict, keys: tuple[str, ...]) -> dict:
    return {key: copy.deepcopy(value[key]) for key in keys if key in value}


def _document(record: dict) -> dict:
    result = _pick(record, ("uri", "state", "revision", "effect", "applied_revision", "merged"))
    validation = record.get("validation")
    if isinstance(validation, dict):
        result["validation"] = _pick(validation, ("state", "revision", "checked_state"))
    if record.get("conflict") not in (None, "none"):
        result.update(_pick(record, ("conflict", "disk_revision", "base_disk_revision", "baseline_known")))
    save = record.get("save", {})
    if save:
        result["save"] = _pick(save, ("state", "previous_uri", "target", "requested"))
    if "live_reload" in record:
        result["live_reload"] = record["live_reload"]
    return result


def project_result(name: str, result: Any) -> Any:
    """Select explicit receipt fields; never mutate a snapshot or execute work."""
    if not isinstance(result, dict) or name not in DOCUMENT_TOOLS or "error" in result or result.get("preview"):
        return copy.deepcopy(result)
    receipt = _pick(result, ("operation_id", "status", "details_retained", "result_query_error", "editor_events"))
    if result.get("status") != "completed":
        receipt.update(_pick(result, ("phase", "resumable", "save_receipt")))
    receipt["documents"] = [_document(record) for record in result.get("documents", [])]
    if result.get("failures"):
        receipt["failures"] = copy.deepcopy(result["failures"])
    if result.get("attachments"):
        receipt["attachments"] = copy.deepcopy(result["attachments"])
    if result.get("connections"):
        receipt["connections"] = copy.deepcopy(result["connections"])
    undo = result.get("undo", {})
    if undo.get("edit_id") is not None or undo.get("retained_files"):
        receipt["undo"] = _pick(undo, ("edit_id",))
        if len(undo.get("steps", [])) > 1:
            receipt["undo"]["steps"] = _pick(undo, ("steps",))["steps"]
        if undo.get("retained_files"):
            receipt["undo"]["retained_files"] = copy.deepcopy(undo["retained_files"])
    # Modified/draft document states already identify routine persistence needs.
    implied = {record["uri"] for record in receipt["documents"] if record.get("state") in {"modified", "draft"}}
    pending_save = [uri for uri in result.get("pending_save", []) if result.get("status") != "completed" or uri not in implied]
    if pending_save:
        receipt["pending_save"] = copy.deepcopy(pending_save)
    return receipt


def result_summary(name: str, result: dict) -> str:
    """Readable text without a second serialized copy of the structured payload."""
    if "error" in result:
        error = result["error"]
        return f"{error.get('code', 'ERROR')}: {error.get('message', 'Request failed.')}"
    operation = result if name == "get_operation_result" else None
    if operation is not None:
        result = operation.get("result", {})
    status = result.get("status", "unknown" if operation is not None else "completed")
    if operation is not None and operation.get("pending") is True:
        status = "pending"
    summary = f"{name}: {status}."
    for key in ("documents", "nodes", "sources", "assets"):
        if isinstance(result.get(key), list):
            summary += f" {len(result[key])} {key}."
            break
    failures = result.get("failures", [])
    if failures:
        summary += " " + "; ".join(f"{item.get('code', 'ERROR')}: {item.get('message', '')}" for item in failures[:3])
        if len(failures) > 3:
            summary += f"; {len(failures) - 3} more failures in the result."
    operation_id = (operation if operation is not None else result).get("operation_id")
    if status == "pending" and operation_id:
        summary += f" Operation: {operation_id}."
    return summary
