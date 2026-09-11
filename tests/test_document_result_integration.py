"""Exercise the canonical document result helper in a real headless Godot runtime."""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in Godot runtime")]

SCRIPT = '''
extends SceneTree
const DocumentResult = preload("res://addons/godot_mcp/document_result.gd")
func _init() -> void:
	var old_record: Dictionary = DocumentResult.document({"uri": "res://doc.gd", "state": "modified", "revision": "current"}, "updated")
	DocumentResult.validation(old_record, {"uri": "res://doc.gd", "revision": "old", "state": "valid", "scope": "snapshot", "entries": [{"kind": "error", "uri": "res://doc.gd", "line": 4, "message": "old diagnostic"}]})
	var matching_record: Dictionary = DocumentResult.document({"uri": "res://doc.gd", "state": "modified", "revision": "current"}, "updated")
	DocumentResult.validation(matching_record, {"uri": "res://doc.gd", "revision": "current", "state": "valid", "scope": "snapshot", "entries": []})
	var merged: Dictionary = DocumentResult.begin({"edit_id": "edit-1", "scope": ["live_sources"]})
	var saved: Dictionary = DocumentResult.document({"uri": "res://doc.gd", "state": "saved", "revision": "current"}, "saved")
	saved.save = {"state": "saved", "index": 1}
	var failed: Dictionary = DocumentResult.document({"uri": "res://doc.gd", "state": "saved", "revision": "current"}, "saved")
	failed.save = {"state": "failed", "index": 0}
	DocumentResult.failure(merged, "save", "EXTERNAL_CHANGE", "A retained failure", {"uri": "res://doc.gd"}, {"tool": "get_context", "arguments": {"scope": "editor"}, "prerequisite": "Resolve conflict"}, {"conflicts": [{"uri": "res://doc.gd"}]})
	merged.pending_save.append("res://doc.gd")
	DocumentResult.put(merged, saved)
	DocumentResult.put(merged, failed)
	DocumentResult.finish(merged, true)
	var modified: Dictionary = DocumentResult.begin()
	var modified_record: Dictionary = DocumentResult.document({"uri": "res://doc.gd", "state": "modified", "revision": "next"}, "updated")
	modified_record.save = {"state": "saved", "index": 2}
	DocumentResult.put(modified, modified_record)
	DocumentResult.finish(modified, true)
	var attachment: Dictionary = DocumentResult.begin()
	DocumentResult.put(attachment, DocumentResult.document({"uri": "res://doc.gd", "state": "saved", "revision": "current"}, "saved"))
	attachment.pending_save.append("res://main.tscn")
	DocumentResult.finish(attachment, true)
	print(JSON.stringify({"old": old_record.validation, "matching": matching_record.validation, "merged": merged, "modified": modified, "attachment": attachment}))
	quit()
'''

def test_document_result_runtime_contract(tmp_path):
    project = tmp_path / "project"
    addon = project / "addons" / "godot_mcp"
    addon.mkdir(parents=True)
    (project / "project.godot").write_text("[application]\nconfig/name=\"DocumentResult\"\n", encoding="utf-8")
    source_addon = os.path.join(os.path.dirname(__file__), os.pardir, "src", "godot_mcp", "addon")
    for name in ("document_result.gd", "operation_result.gd"):
        shutil.copy2(os.path.join(source_addon, name), addon / name)
    script = project / "document_result_probe.gd"
    script.write_text(SCRIPT, encoding="utf-8")
    completed = subprocess.run([os.environ.get("GODOT", "godot"), "--headless", "--path", str(project), "--script", str(script)], check=False, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(next(line for line in reversed(completed.stdout.splitlines()) if line.startswith("{")))
    assert payload["old"]["state"] == "pending" and payload["old"]["checked_state"] == "valid" and payload["old"]["revision"] == "old"
    assert payload["old"]["entries"][0]["message"] == "old diagnostic" and "uri" not in payload["old"]["entries"][0]
    assert payload["matching"]["state"] == "valid" and "revision" not in payload["matching"]
    merged = payload["merged"]
    assert len(merged["documents"]) == 1
    assert [a["index"] for a in merged["documents"][0]["save"]["attempts"]] == [0, 1] and merged["documents"][0]["save"]["state"] == "saved"
    assert merged["pending_save"] == []
    assert merged["failures"][0]["recovery"]["arguments"] == {"scope": "editor"} and merged["failures"][0]["details"]["conflicts"] == [{"uri": "res://doc.gd"}]
    assert merged["undo"] == {"edit_id": "edit-1", "scope": ["live_sources"]}
    assert payload["modified"]["pending_save"] == ["res://doc.gd"]
    assert payload["attachment"]["pending_save"] == ["res://main.tscn"]
