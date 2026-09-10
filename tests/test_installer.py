import json
from pathlib import Path

import pytest

from godot_mcp import installer


def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "addons/godot_mcp").mkdir(parents=True)
    (root / "addons/godot_mcp/plugin.cfg").write_text("old addon")
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
    config = tmp_path / "client.json"
    config.write_text(json.dumps({"keep": {"value": 1}}))
    old_project = (root / "project.godot").read_bytes()
    old_addon = (root / "addons/godot_mcp/plugin.cfg").read_bytes()
    executable = tmp_path / "environment/bin/godot-mcp"
    home = tmp_path / "home"
    record = installer.install_project(root, executable, home, config)
    assert record["status"] == "installed"
    assert b"old addon" not in (root / "addons/godot_mcp/plugin.cfg").read_bytes()
    assert json.loads(config.read_text())["keep"] == {"value": 1}
    restored = installer.rollback(Path(record["backup"]))
    assert restored["status"] == "rolled_back"
    assert (root / "project.godot").read_bytes() == old_project
    assert (root / "addons/godot_mcp/plugin.cfg").read_bytes() == old_addon
    assert json.loads(config.read_text()) == {"keep": {"value": 1}}


def test_install_project_rolls_back_everything_when_registration_fails(tmp_path, monkeypatch):
    root = project(tmp_path)
    config = tmp_path / "client.json"
    config.write_text('{"keep": true}\n')
    old_project = (root / "project.godot").read_bytes()
    old_addon = (root / "addons/godot_mcp/plugin.cfg").read_bytes()
    old_config = config.read_bytes()

    def fail(*args, **kwargs):
        raise ValueError("registration failed")

    monkeypatch.setattr(installer, "register_client", fail)
    with pytest.raises(ValueError, match="registration failed"):
        installer.install_project(root, tmp_path / "server", tmp_path / "home", config)
    assert (root / "project.godot").read_bytes() == old_project
    assert (root / "addons/godot_mcp/plugin.cfg").read_bytes() == old_addon
    assert config.read_bytes() == old_config
