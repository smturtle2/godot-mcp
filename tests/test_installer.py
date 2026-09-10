import json
from pathlib import Path

import pytest

from godot_mcp import installer
from godot_mcp.bridge import ToolError


def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "addons/godot_mcp").mkdir(parents=True)
    (root / "addons/godot_mcp/plugin.cfg").write_text("old addon")
    (root / ".godot-mcp").mkdir()
    (root / "project.godot").write_text("[application]\nconfig/name=Keep\n")
    return root


def test_enable_plugin_preserves_sections_plugins_and_is_idempotent():
    source = ('[application]\nconfig/name="Demo"\n\n[editor_plugins]\n'
              'enabled=PackedStringArray("res://addons/other/plugin.cfg", "res://addons/godot_mcp/plugin.cfg")\n'
              '\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
    once = installer.enable_plugin(source)
    assert once == source
    assert installer.enable_plugin(once) == once

    missing = installer.enable_plugin('[application]\nconfig/name="Demo"\n\n[editor_plugins]\n\n[rendering]\nfoo=1\n')
    assert '"res://addons/godot_mcp/plugin.cfg"' in missing
    assert '[rendering]\nfoo=1' in missing


def test_enable_plugin_handles_multiline_array_and_rejects_invalid_syntax():
    source = ('[editor_plugins]\n enabled = PackedStringArray(\n'
              '"res://addons/one/plugin.cfg",\n"res://addons/two/plugin.cfg"\n)\n\n[application]\nname="x"\n')
    updated = installer.enable_plugin(source)
    assert 'res://addons/godot_mcp/plugin.cfg' in updated
    assert '[application]' in updated
    assert updated.count('enabled') == 1
    assert 'res://addons/one/plugin.cfg' in updated and 'res://addons/two/plugin.cfg' in updated
    with pytest.raises(ValueError, match="Unsupported"):
        installer.enable_plugin('[editor_plugins]\nenabled=["res://addons/other/plugin.cfg"]\n')


def test_install_project_preserves_old_state_and_explicit_rollback(tmp_path):
    root = project(tmp_path)
    old_project = (root / "project.godot").read_bytes()
    old_addon = (root / "addons/godot_mcp/plugin.cfg").read_bytes()
    executable = tmp_path / "environment/bin/godot-mcp"
    home = tmp_path / "home"
    record = installer.install_project(root, executable, home)
    assert record["status"] == "installed"
    assert b"old addon" not in (root / "addons/godot_mcp/plugin.cfg").read_bytes()
    restored = installer.rollback(Path(record["backup"]))
    assert restored["status"] == "rolled_back"
    assert (root / "project.godot").read_bytes() == old_project
    assert (root / "addons/godot_mcp/plugin.cfg").read_bytes() == old_addon


def test_install_project_rolls_back_everything_when_link_write_fails(tmp_path, monkeypatch):
    root = project(tmp_path)
    old_project = (root / "project.godot").read_bytes()
    old_addon = (root / "addons/godot_mcp/plugin.cfg").read_bytes()
    def fail(*args, **kwargs):
        raise ValueError("link write failed")

    monkeypatch.setattr(installer, "_atomic_write", fail)
    with pytest.raises(ValueError, match="link write failed"):
        installer.install_project(root, tmp_path / "server", tmp_path / "home")
    assert (root / "project.godot").read_bytes() == old_project
    assert (root / "addons/godot_mcp/plugin.cfg").read_bytes() == old_addon


def test_stale_previous_version_endpoint_allows_install(monkeypatch, tmp_path):
    root = project(tmp_path)
    endpoint = root / ".godot-mcp/endpoint.json"
    endpoint.write_text(json.dumps({"project": str(root), "pid": 12345, "version": "v4.7.2_0"}))
    monkeypatch.setattr(installer.psutil, "pid_exists", lambda pid: False)
    record = installer.install_project(root, tmp_path / "server", tmp_path / "home")
    assert record["status"] == "installed"


def test_live_previous_version_endpoint_blocks_before_edits(monkeypatch, tmp_path):
    root = project(tmp_path)
    old_project = (root / "project.godot").read_bytes()
    old_addon = (root / "addons/godot_mcp/plugin.cfg").read_bytes()
    (root / ".godot-mcp/endpoint.json").write_text(json.dumps({"project": str(root), "pid": 12345, "version": "v4.7.2_0"}))
    monkeypatch.setattr(installer.psutil, "pid_exists", lambda pid: True)

    async def mismatch(*_args, **_kwargs):
        raise ToolError("VERSION_MISMATCH", "old plugin")

    monkeypatch.setattr("godot_mcp.bridge.EditorBridge.call", mismatch)
    with pytest.raises(ValueError, match="Close this project"):
        installer.install_project(root, tmp_path / "server", tmp_path / "home")
    assert (root / "project.godot").read_bytes() == old_project
    assert (root / "addons/godot_mcp/plugin.cfg").read_bytes() == old_addon


@pytest.mark.parametrize("payload", ["{bad", "[]"])
def test_malformed_endpoint_is_actionable_and_non_mutating(tmp_path, payload):
    root = project(tmp_path)
    old_project = (root / "project.godot").read_bytes()
    old_addon = (root / "addons/godot_mcp/plugin.cfg").read_bytes()
    (root / ".godot-mcp/endpoint.json").write_text(payload)
    with pytest.raises(ValueError, match="endpoint"):
        installer.install_project(root, tmp_path / "server", tmp_path / "home")
    assert (root / "project.godot").read_bytes() == old_project
    assert (root / "addons/godot_mcp/plugin.cfg").read_bytes() == old_addon
