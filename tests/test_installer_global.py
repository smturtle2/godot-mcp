import json
from pathlib import Path

import pytest

from godot_mcp import installer


def setup_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "addons/godot_mcp").mkdir(parents=True)
    (project / "addons/godot_mcp/old.txt").write_text("old")
    (project / ".godot-mcp").mkdir()
    (project / "project.godot").write_text("config_version=5\n")
    return project


def test_global_install_registers_home_without_project(tmp_path):
    home, config, executable = tmp_path / "home", tmp_path / "client.json", tmp_path / "server"
    executable.write_text("fake")
    record = installer.install_global(executable, home, config=config)
    assert record["status"] == "installed"
    entry = json.loads(config.read_text())["mcpServers"]["godot-mcp"]
    assert entry["args"] == ["connect", "--home", str(home.resolve())]
    assert "project" not in entry["args"]


def test_global_update_refreshes_existing_link_without_project_argument(tmp_path):
    project, home, config = setup_project(tmp_path), tmp_path / "home", tmp_path / "client.json"
    first_executable, second_executable = tmp_path / "server1", tmp_path / "server2"
    first_executable.write_text("one")
    second_executable.write_text("two")
    installer.install_global(first_executable, home, project, config)
    old_link = json.loads((project / ".godot-mcp/install.json").read_text())
    record = installer.install_global(second_executable, home)
    new_link = json.loads((project / ".godot-mcp/install.json").read_text())
    assert record["status"] == "installed"
    assert old_link["home"] == new_link["home"] == str(home.resolve())
    assert json.loads((home / "active.json").read_text())["executable"] == str(second_executable)


def test_global_rollback_restores_active_config_plugin_link_and_index(tmp_path):
    project, home, config = setup_project(tmp_path), tmp_path / "home", tmp_path / "client.json"
    executable = tmp_path / "server"
    executable.write_text("server")
    config.write_text('{"keep": true}\n')
    old_plugin = (project / "addons/godot_mcp/old.txt").read_bytes()
    record = installer.install_global(executable, home, project, config)
    installer.rollback(Path(record["backup"]))
    assert not (home / "active.json").exists()
    assert config.read_text() == '{"keep": true}\n'
    assert (project / "addons/godot_mcp/old.txt").read_bytes() == old_plugin
    assert not (project / ".godot-mcp/install.json").exists()
    assert list((home / "projects").glob("*.json")) == []


def test_global_registration_failure_rolls_back_all_children_and_files(tmp_path, monkeypatch):
    project, home, config = setup_project(tmp_path), tmp_path / "home", tmp_path / "client.json"
    executable = tmp_path / "server"
    executable.write_text("server")
    config.write_text('{"keep": true}\n')

    def fail(*_args, **_kwargs):
        raise ValueError("registration failed")

    monkeypatch.setattr(installer, "register_global_client", fail)
    with pytest.raises(ValueError, match="registration failed"):
        installer.install_global(executable, home, project, config)
    assert config.read_text() == '{"keep": true}\n'
    assert not (project / ".godot-mcp/install.json").exists()
    assert not (home / "active.json").exists()


def test_global_install_rejects_non_object_client_json_without_mutation(tmp_path):
    home, config = tmp_path / "home", tmp_path / "client.json"
    config.write_text("[]")
    with pytest.raises(ValueError):
        installer.install_global(tmp_path / "server", home, config=config)
    assert config.read_text() == "[]"

