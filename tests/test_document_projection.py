from __future__ import annotations

import copy

from jsonschema import Draft202012Validator

from godot_mcp.catalog import DOCUMENT_OUTPUT
from godot_mcp.result_projection import project_result


def document(uri: str = "res://a.gd", *, effect: str = "updated", state: str = "modified") -> dict:
    return {"uri": uri, "effect": effect, "state": state, "revision": "current",
            "disk_revision": "disk", "base_disk_revision": "disk", "baseline_known": True,
            "conflict": "none", "validation": {"state": "valid", "scope": "snapshot", "entries": []}}


def canonical(*documents: dict, status: str = "completed") -> dict:
    return {"operation_id": "operation-test-1", "details_retained": True, "status": status, "complete": status == "completed", "documents": list(documents),
            "failures": [], "pending": [], "pending_save": [], "attachments": [],
            "undo": {"edit_id": "edit-1", "scope": ["live_sources"], "retained_files": []},
            "validation_snapshot": "snapshot-1"}


def save_failure(uri: str, index: int = 0) -> dict:
    return {"phase": "save", "code": "EXTERNAL_CHANGE", "message": "Disk changed.", "uri": uri,
            "details": {"index": index, "conflicts": [{"uri": uri, "base_disk_revision": "old", "disk_revision": "new"}]},
            "recovery": {"tool": "get_context", "arguments": {"scope": "editor"},
                         "prerequisite": "Reconcile the source and disk before saving."}}


def test_receipt_uses_explicit_essential_fields_without_mutating_snapshot():
    value = canonical(document())
    value.update(pending_save=["res://a.gd"], phase="completed", phases={"save": "done"}, resumable=False,
                 runtime={"state": "confirmed"}, runtime_application="constant long explanation",
                 future_detail={"verbose": True})
    value["undo"]["steps"] = [{"edit_id": "edit-1", "scope": "live_sources"}]
    original = copy.deepcopy(value)
    receipt = project_result("apply_script_changes", value)
    assert value == original
    assert receipt == {
        "operation_id": "operation-test-1", "details_retained": True, "status": "completed",
        "state_summary": {"applied": "1/1", "diagnostics": "valid"},
        "documents": [{"uri": "res://a.gd", "effect": "updated", "state": "modified", "revision": "current", "validation": {"state": "valid"}}],
        "undo": {"edit_id": "edit-1"},
    }
    receipt["documents"][0]["revision"] = "changed receipt"
    assert value == original
    Draft202012Validator(DOCUMENT_OUTPUT).validate(receipt)


def test_receipt_preserves_conflicts_stale_validation_and_recovery():
    record = document()
    record.update(conflict="external_change", disk_revision="new", base_disk_revision="old", applied_revision="applied")
    record["validation"] = {"state": "pending", "checked_state": "invalid", "revision": "checked",
                            "scope": "snapshot", "entries": [{"kind": "error", "message": "Invalid source", "line": 4}]}
    value = canonical(record, status="partial")
    value.update(pending_save=[record["uri"]], failures=[save_failure(record["uri"])], save_observation="observed source buffers")
    brief = project_result("apply_script_changes", value)
    projected = brief["documents"][0]
    for key in ("uri", "revision", "applied_revision", "conflict", "disk_revision", "base_disk_revision", "baseline_known"):
        assert projected[key] == record[key]
    assert projected["validation"] == {"state": "pending", "checked_state": "invalid", "revision": "checked"}
    for key in ("status", "failures", "pending_save"):
        assert brief[key] == value[key]
    assert brief["undo"] == {"edit_id": "edit-1"}
    assert brief["state_summary"]["diagnostics"] == "stale"
    Draft202012Validator(DOCUMENT_OUTPUT).validate(brief)


def test_unknown_tools_and_error_envelopes_pass_through_as_copies():
    for name, value in [("create_script", {"error": {"code": "X", "message": "failure"}}), ("other", {"x": [1]})]:
        projected = project_result(name, value)
        assert projected == value and projected is not value


def test_created_source_attachment_and_stale_verdict_keep_separate_boundaries():
    record = document(effect="created")
    record.update(applied_revision="written", save={"state": "saved"}, live_reload="not_attempted")
    record["validation"] = {"state": "pending", "checked_state": "valid", "revision": "written", "scope": "snapshot",
                            "entries": [{"kind": "warning", "message": "Changed after validation.", "line": 0}]}
    node = {"scene": "res://main.tscn", "path": "."}
    attachment = {"script": {"uri": record["uri"], "node": node}}
    recovery = {"tool": "update_nodes", "arguments": {"changes": [{"node": node, "set": {"script": {"$type": "Resource", "uri": record["uri"]}}}]},
                "prerequisite": "Repair source first."}
    value = canonical(record, status="partial")
    value.update(attachments=[attachment], failures=[{"phase": "bindings", "code": "INCOMPATIBLE_BASE", "message": "Cannot attach.", "node": node, "recovery": recovery}],
                 pending_save=[record["uri"], node["scene"]], undo={"edit_id": "attach-1", "scope": ["attachments"],
                 "retained_files": [record["uri"]], "steps": [{"edit_id": "source-1", "scope": "live_sources"},
                 {"edit_id": "attach-1", "scope": "attachments"}]})
    projected = project_result("apply_script_changes", value)
    Draft202012Validator(DOCUMENT_OUTPUT).validate(projected)
    current = projected["documents"][0]
    assert current["state"] == "modified" and current["save"]["state"] == "saved"
    assert current["revision"] == "current" and current["applied_revision"] == "written"
    assert current["validation"] == {"state": "pending", "checked_state": "valid", "revision": "written"}
    for key in ("attachments", "failures", "pending_save"):
        assert projected[key] == value[key]
    assert projected["undo"] == {"edit_id": "attach-1", "retained_files": [record["uri"]], "steps": [
        {"edit_id": "source-1", "scope": "live_sources"}, {"edit_id": "attach-1", "scope": "attachments"}]}


def test_save_as_identity_and_observed_saves_survive_while_history_stays_in_snapshot():
    first = {"uri": "res://new.gd", "effect": "saved", "state": "saved", "revision": "new",
             "save": {"state": "saved", "index": 2, "previous_uri": "res://old.gd"}}
    repeated = {"uri": "res://repeated.tscn", "effect": "saved", "save": {"state": "failed", "index": 1,
                "attempts": [{"state": "saved", "index": 0}, {"state": "failed", "index": 1}]}}
    related = {"uri": "res://linked.gd", "save": {"state": "saved", "requested": False}}
    value = canonical(first, repeated, related, status="partial")
    value.update(failures=[save_failure(repeated["uri"], 1)], pending_save=[repeated["uri"]],
                 save_observation="observed source buffers", undo={"edit_id": None, "scope": [], "note": "Disk writes are retained."})
    projected = project_result("save_documents", value)
    Draft202012Validator(DOCUMENT_OUTPUT).validate(projected)
    assert projected["documents"][0]["save"] == {"state": "saved", "previous_uri": "res://old.gd"}
    assert projected["documents"][1]["save"] == {"state": "failed"}
    assert projected["documents"][2] == related
    assert len(value["documents"][1]["save"]["attempts"]) == 2
    assert "undo" not in projected and "save_observation" not in projected
    for key in ("status", "failures", "pending_save"):
        assert projected[key] == value[key]
