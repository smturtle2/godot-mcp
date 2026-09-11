"""Behavioral coverage for bounded, inert operation result records."""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in Godot runtime"),
]


SCRIPT = r'''
extends SceneTree
const OperationRecords = preload("res://addons/godot_mcp/operation_records.gd")

class FakeHost:
    extends RefCounted
    var epoch: String = "epoch-a"
    var undo_state: Dictionary = {"available": true}
    func fail(code: String, message: String, details: Dictionary = {}) -> Dictionary:
        return {"error": {"code": code, "message": message, "details": details}}
    func undo_availability(edit_id: Variant) -> Dictionary:
        var result := undo_state.duplicate(true)
        result["edit_id"] = edit_id
        return result

func check(ok: bool, label: String, failures: Array) -> void:
    if not ok: failures.append(label)

func _init() -> void:
    var failures: Array = []
    var host := FakeHost.new()
    var records := OperationRecords.new(host)

    var first: Dictionary = records.begin("probe")
    var first_id: String = first.operation_id
    var published := {"value": {"nested": 1}, "undo": {"edit_id": "edit-a"}}
    check(records.publish(first_id, published), "publish", failures)
    published.value.nested = 99
    var read_one: Dictionary = records.get_result(first_id)
    check(read_one.snapshot and read_one.operation_id != read_one.result.undo.edit_id, "identity fields", failures)
    check(read_one.result.value.nested == 1, "immutable saved JSON", failures)
    read_one.result.value.nested = 77
    var read_two: Dictionary = records.get_result(first_id)
    check(read_two.result.value.nested == 1, "read is inert", failures)
    check(read_two.recorded_at_usec == read_one.recorded_at_usec, "read does not republish", failures)
    check(read_two.current_undo.edit_id == "edit-a", "current undo lookup", failures)
    host.undo_state = {"available": false}
    var read_three: Dictionary = records.get_result(first_id)
    check(not read_three.current_undo.available and read_three.result.value.nested == 1, "live undo separate from snapshot", failures)

    records.max_records = 2
    var completed := records.begin("completed")
    check(records.publish(completed.operation_id, {"n": 1}), "completed publish", failures)
    var pending := records.begin("pending")
    var retained := records.begin("next")
    check(not retained.has("error") and records.records.has(pending.operation_id), "completed evicted before pending", failures)
    check(records.get_result(completed.operation_id).error.code == "OPERATION_RESULT_EXPIRED", "count eviction expired", failures)
    var blocked := records.begin("blocked")
    check(blocked.error.code == "OPERATION_LIMIT" and records.records.size() == 2, "all pending blocks begin", failures)

    records = OperationRecords.new(host)
    records.max_bytes = 80
    var byte_a := records.begin("byte-a")
    records.publish(byte_a.operation_id, {"payload": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"})
    var byte_b := records.begin("byte-b")
    records.publish(byte_b.operation_id, {"payload": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"})
    check(records.records.size() == 1 and records.records.has(byte_b.operation_id), "byte eviction completed first", failures)

    records = OperationRecords.new(host)
    records.max_bytes = 16
    var oversized := records.begin("oversized")
    check(not records.publish(oversized.operation_id, {"payload": "too large"}), "oversized completed publish", failures)
    check(records.get_result(oversized.operation_id).error.code == "OPERATION_RESULT_EXPIRED", "oversized completed expires", failures)
    var recover := records.begin("recover")
    check(not records.publish(recover.operation_id, {"payload": "pending result too large"}, true), "oversized pending retained", failures)
    check(records.get_result(recover.operation_id).error.code == "OPERATION_RESULT_UNAVAILABLE", "oversized pending unavailable", failures)
    check(records.publish(recover.operation_id, {"ok": true}, false), "pending later recovers", failures)
    check(records.get_result(recover.operation_id).result.ok, "recovered result available", failures)

    records = OperationRecords.new(host)
    var known := records.begin("known")
    records.publish(known.operation_id, {"ok": true})
    check(records.get_result("operation-other-1").error.code == "OPERATION_NOT_FOUND", "wrong epoch not found", failures)
    check(records.get_result("operation-epoch-a-999").error.code == "OPERATION_NOT_FOUND", "future sequence not found", failures)
    check(records.get_result("unknown").error.code == "OPERATION_NOT_FOUND", "unknown id not found", failures)

    print(JSON.stringify({"failures": failures}))
    quit(1 if not failures.is_empty() else 0)
'''


def test_operation_records_runtime_contract(tmp_path):
    project = tmp_path / "project"
    addon = project / "addons" / "godot_mcp"
    addon.mkdir(parents=True)
    source = os.path.join(os.path.dirname(__file__), os.pardir, "src", "godot_mcp", "addon", "operation_records.gd")
    shutil.copy2(source, addon / "operation_records.gd")
    (project / "project.godot").write_text('[application]\nconfig/name="OperationRecords"\n', encoding="utf-8")
    script = project / "operation_records_probe.gd"
    script.write_text(SCRIPT, encoding="utf-8")
    result = subprocess.run(
        [os.environ.get("GODOT", "godot"), "--headless", "--path", str(project), "--script", "res://operation_records_probe.gd"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(next(line for line in reversed(result.stdout.splitlines()) if line.startswith("{")))
    assert payload["failures"] == []
