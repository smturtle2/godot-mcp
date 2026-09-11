"""The small mutation receipt; canonical operation snapshots stay in Godot."""
from __future__ import annotations

import copy
from typing import Any

from .catalog import DOCUMENT_TOOLS


def _pick(value: dict, keys: tuple[str, ...]) -> dict:
    return {key: copy.deepcopy(value[key]) for key in keys if key in value}


def _document(record: dict) -> dict:
    result = _pick(record, ("uri", "state", "revision", "effect", "applied_revision"))
    validation = record.get("validation")
    if isinstance(validation, dict):
        result["validation"] = _pick(validation, ("state", "revision", "checked_state"))
    if record.get("conflict") not in (None, "none"):
        result.update(_pick(record, ("conflict", "disk_revision", "base_disk_revision", "baseline_known")))
    save = record.get("save", {})
    if save and (record.get("state") != "saved" or save.get("state") in {"failed", "skipped"}
                 or any(key in save for key in ("previous_uri", "target")) or save.get("requested") is False):
        result["save"] = _pick(save, ("state", "previous_uri", "target", "requested"))
    if record.get("live_reload") in {"failed", "deferred"}:
        result["live_reload"] = record["live_reload"]
    return result


def project_result(name: str, result: Any) -> Any:
    """Select explicit receipt fields; never mutate a snapshot or execute work."""
    if not isinstance(result, dict) or name not in DOCUMENT_TOOLS or "error" in result:
        return copy.deepcopy(result)
    receipt = _pick(result, ("operation_id", "status", "details_retained"))
    receipt["documents"] = [_document(record) for record in result.get("documents", [])]
    if result.get("failures"):
        receipt["failures"] = copy.deepcopy(result["failures"])
    if result.get("attachments"):
        receipt["attachments"] = copy.deepcopy(result["attachments"])
    undo = result.get("undo", {})
    if undo.get("edit_id") is not None or undo.get("retained_files"):
        receipt["undo"] = _pick(undo, ("edit_id", "scope", "retained_files"))
    # Modified/draft document states already identify routine persistence needs.
    implied = {record["uri"] for record in receipt["documents"] if record.get("state") in {"modified", "draft"}}
    pending_save = [uri for uri in result.get("pending_save", []) if result.get("status") != "completed" or uri not in implied]
    if pending_save:
        receipt["pending_save"] = copy.deepcopy(pending_save)
    if result.get("pending"):
        receipt["pending"] = copy.deepcopy(result["pending"])
    return receipt
