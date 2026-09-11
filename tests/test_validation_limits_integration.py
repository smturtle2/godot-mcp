"""Real-engine regression coverage for snapshot autoload isolation."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real engine"
)]


async def test_snapshot_diagnostics_do_not_start_declared_autoload(tmp_path):
    target = tmp_path / "target"
    harness = tmp_path / "harness"
    addon_source = Path(__file__).parents[1] / "src/godot_mcp/addon"
    shutil.copytree(Path(__file__).parent / "fixtures", target)
    shutil.copytree(addon_source, target / "addons/godot_mcp")
    harness.mkdir()

    marker = (tmp_path / "autoload-started.marker").resolve()
    (target / "autoload_probe.gd").write_text(
        "@tool\nextends Node\n\nfunc _init() -> void:\n"
        f'\tFileAccess.open({json.dumps(marker.as_posix())}, FileAccess.WRITE)\n',
        encoding="utf-8",
    )
    (target / "dependent.gd").write_text(
        "@tool\nextends Node\n\nfunc uses_probe() -> Variant:\n\treturn SnapshotProbe\n",
        encoding="utf-8",
    )
    project_file = target / "project.godot"
    project_file.write_text(
        project_file.read_text(encoding="utf-8")
        + '\n[autoload]\nSnapshotProbe="*res://autoload_probe.gd"\n',
        encoding="utf-8",
    )
    shutil.copy2(addon_source / "source_validation.gd", harness / "source_validation.gd")
    result_file = harness / "result.json"
    (harness / "harness.gd").write_text(
        "extends SceneTree\n"
        "const SourceValidation = preload(\"res://source_validation.gd\")\n\n"
        "func _init() -> void:\n"
        f'\tvar result: Dictionary = SourceValidation.new(null)._run({json.dumps(target.as_posix())}, OS.get_executable_path(), ["res://dependent.gd"], {{}}, {{}})\n'
        f'\tvar file := FileAccess.open({json.dumps(result_file.as_posix())}, FileAccess.WRITE)\n'
        "\tfile.store_string(JSON.stringify(result))\n"
        "\tfile.close()\n"
        "\tquit()\n",
        encoding="utf-8",
    )
    (harness / "project.godot").write_text(
        'config_version=5\n\n[application]\nconfig/name="Validation harness"\n',
        encoding="utf-8",
    )
    assert not marker.exists()

    completed = subprocess.run(
        [os.environ.get("GODOT", "godot"), "--headless", "--path", str(harness), "--script", "res://harness.gd"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(result_file.read_text(encoding="utf-8"))
    source = result["sources"][0]
    assert source["uri"] == "res://dependent.gd"
    assert source["state"] == "unavailable"
    assert source["valid"] is None
    assert "autoload singleton" in source["entries"][0]["message"]
    assert "SnapshotProbe" in source["entries"][0]["message"]
    assert not marker.exists()
