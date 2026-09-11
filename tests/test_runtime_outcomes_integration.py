"""Runtime operation outcome regressions against a real headless Godot."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real Godot runtime"
)]


def test_send_input_preserves_applied_effects_and_nested_failures(tmp_path):
    project = tmp_path / "project"
    addon = project / "addons" / "godot_mcp"
    addon.mkdir(parents=True)
    source_addon = Path(__file__).parents[1] / "src" / "godot_mcp" / "addon"
    for name in ("runtime.gd", "codec.gd", "log_buffer.gd", "operation_result.gd"):
        shutil.copy2(source_addon / name, addon / name)
    (project / "project.godot").write_text("config_version=5\n[application]\nconfig/name=\"outcome test\"\n")
    (project / "probe.gd").write_text(
        '''extends SceneTree
const Runtime = preload("res://addons/godot_mcp/runtime.gd")

func _initialize() -> void:
    var helper := Runtime.new()
    root.add_child(helper)
    await process_frame
    var failed := await helper.send_input({"events": [{"event": {"action": {"action": "ui_accept", "pressed": true}}}], "wait_for": {"property": {"node": {"path": "/root"}, "property": "definitely_missing"}}, "timeout_ms": 10, "capture_after": true})
    print("FAILED=" + str(failed))
    assert(failed.processed == 1)
    assert(failed.held_inputs == 1)
    assert(failed.status == "partial" and not failed.complete)
    assert(failed.failures.size() == 2)
    assert(failed.failures[0].phase == "condition")
    assert(failed.failures[0].code == "PROPERTY_NOT_FOUND")
    assert(failed.failures[1].phase == "capture")
    assert(failed.failures[1].code == "RENDERER_UNAVAILABLE")
    var success := await helper.send_input({"events": [{"event": {"action": {"action": "ui_accept", "pressed": false}}}]})
    print("SUCCESS=" + str(success))
    assert(success.processed == 1 and success.held_inputs == 0)
    assert(success.status == "completed" and success.complete)
    var timed := await helper.send_input({"events": [{"event": {"key": {"key": "Enter", "pressed": true}}}], "wait_for": {"node": {"node": {"path": "/root/Missing"}, "exists": true}}, "timeout_ms": 20})
    print("TIMED=" + str(timed))
    assert(timed.processed == 1 and timed.held_inputs == 1)
    assert(timed.condition.timed_out)
    assert(timed.status == "partial" and not timed.complete)
    assert(timed.failures.size() == 1 and timed.failures[0].phase == "condition" and timed.failures[0].code == "CONDITION_TIMEOUT")
    await helper.send_input({"events": [{"event": {"key": {"key": "Enter", "pressed": false}}}]})
    var observation := await helper.wait_condition({"node": {"node": {"path": "/root/Missing"}, "exists": true}}, 20, 5)
    print("OBSERVATION=" + str(observation))
    assert(not observation.satisfied and observation.timed_out and not observation.has("error"))
    print("RUNTIME_OUTCOME_OK")
    quit(0)
'''
    )
    result = subprocess.run(
        [os.environ.get("GODOT", "godot"), "--headless", "--path", str(project), "--script", "res://probe.gd"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAILED=" in result.stdout and "SUCCESS=" in result.stdout and "TIMED=" in result.stdout and "OBSERVATION=" in result.stdout and "RUNTIME_OUTCOME_OK" in result.stdout
