"""Focused diagnostics cursor and kind-filter regressions in Godot."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real Godot runtime"
)]


def test_log_buffer_filters_before_limit_and_preserves_source_verdict(tmp_path):
    project = tmp_path / "project"
    addon = project / "addons" / "godot_mcp"
    addon.mkdir(parents=True)
    source_addon = Path(__file__).parents[1] / "src" / "godot_mcp" / "addon"
    for name in ("runtime.gd", "source_manifest.gd", "codec.gd", "log_buffer.gd", "operation_result.gd"):
        shutil.copy2(source_addon / name, addon / name)
    (project / "project.godot").write_text("config_version=5\n[application]\nconfig/name=\"log test\"\n")
    (project / "probe.gd").write_text(
        '''extends SceneTree
const LogBuffer = preload("res://addons/godot_mcp/log_buffer.gd")
const Runtime = preload("res://addons/godot_mcp/runtime.gd")
func _initialize() -> void:
    var logs := LogBuffer.new()
    logs._append("warning", "w1")
    logs._append("error", "e1")
    logs._append("log", "l1")
    logs._append("error", "e2")
    var first: Dictionary = logs.read(0, 1, ["error"])
    var second: Dictionary = logs.read(first.cursor, 1, ["error"])
    var empty: Dictionary = logs.read(second.cursor, 1, ["warning"])
    var source: Array = LogBuffer.filter_entries([{"kind": "warning"}, {"kind": "error"}], ["error"])
    var helper := Runtime.new()
    root.add_child(helper)
    await process_frame
    helper.logs = logs
    var runtime: Dictionary = await helper.dispatch("get_diagnostics", {"since": 0, "limit": 1, "kinds": ["error"]})
    print("FIRST=" + str(first))
    print("SECOND=" + str(second))
    print("EMPTY=" + str(empty))
    print("SOURCE_COUNT=" + str(source.size()))
    print("RUNTIME=" + str(runtime))
    quit()
'''
    )
    result = subprocess.run(
        [os.environ.get("GODOT", "godot"), "--headless", "--path", str(project), "--script", "res://probe.gd"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SOURCE_COUNT=1" in result.stdout
    assert "FIRST=" in result.stdout and '"has_more": true' in result.stdout
    assert "SECOND=" in result.stdout and '"has_more": false' in result.stdout
    assert "EMPTY=" in result.stdout and '"entries": []' in result.stdout
    assert "RUNTIME=" in result.stdout
    assert '"kind": "error"' in result.stdout
    assert '"kind": "warning"' not in result.stdout.split("RUNTIME=", 1)[1]
