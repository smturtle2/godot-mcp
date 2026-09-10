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


def test_global_install_activates_server_without_project(tmp_path):
    home, executable = tmp_path / "home", tmp_path / "server"
    executable.write_text("fake")
    record = installer.install_global(executable, home)
    assert record["status"] == "installed"
    assert json.loads((home / "active.json").read_text())["executable"] == str(executable)


def test_global_update_refreshes_existing_link_without_project_argument(tmp_path):
    project, home = setup_project(tmp_path), tmp_path / "home"
    first_executable, second_executable = tmp_path / "server1", tmp_path / "server2"
    first_executable.write_text("one")
    second_executable.write_text("two")
    installer.install_global(first_executable, home, project)
    old_link = json.loads((project / ".godot-mcp/install.json").read_text())
    record = installer.install_global(second_executable, home)
    new_link = json.loads((project / ".godot-mcp/install.json").read_text())
    assert record["status"] == "installed"
    assert old_link["home"] == new_link["home"] == str(home.resolve())
    assert json.loads((home / "active.json").read_text())["executable"] == str(second_executable)


def test_global_rollback_restores_active_config_plugin_link_and_index(tmp_path):
    project, home = setup_project(tmp_path), tmp_path / "home"
    executable = tmp_path / "server"
    executable.write_text("server")
    old_plugin = (project / "addons/godot_mcp/old.txt").read_bytes()
    record = installer.install_global(executable, home, project)
    installer.rollback(Path(record["backup"]))
    assert not (home / "active.json").exists()
    assert (project / "addons/godot_mcp/old.txt").read_bytes() == old_plugin
    assert not (project / ".godot-mcp/install.json").exists()
    assert list((home / "projects").glob("*.json")) == []


def test_global_activation_failure_rolls_back_all_children_and_files(tmp_path, monkeypatch):
    project, home = setup_project(tmp_path), tmp_path / "home"
    executable = tmp_path / "server"
    executable.write_text("server")

    original_write = installer._atomic_write

    def fail(path, *args, **kwargs):
        if path == home / "active.json":
            raise ValueError("activation failed")
        return original_write(path, *args, **kwargs)

    monkeypatch.setattr(installer, "_atomic_write", fail)
    with pytest.raises(ValueError, match="activation failed"):
        installer.install_global(executable, home, project)
    assert not (project / ".godot-mcp/install.json").exists()
    assert not (home / "active.json").exists()


def test_legacy_client_registry_is_ignored_without_mutation(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    legacy = home / "clients.json"
    legacy.write_text("not json")
    installer.install_global(tmp_path / "server", home)
    assert legacy.read_text() == "not json"


def test_updates_and_legacy_rollbacks_never_access_external_settings(tmp_path, monkeypatch):
    home, project = tmp_path / 'home', setup_project(tmp_path)
    home.mkdir()
    external = tmp_path / 'external-app.json'
    external.write_text('user-owned settings')
    legacy = home / 'clients.json'
    legacy.write_text(json.dumps([{'path': str(external), 'format': 'json', 'name': 'old'}]))
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if path in (external, legacy):
            raise AssertionError('Installer accessed client-owned settings')
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', guarded_open)
    first = installer.install_global(tmp_path / 'server1', home, project)
    second = installer.install_global(tmp_path / 'server2', home)
    # Old journals contain app snapshots and per-project registration fields.
    backup = Path(second['backup'])
    journal = json.loads((backup / 'transaction.json').read_text())
    journal['snapshots'].append({'path': str(external), 'backup': None})
    journal['snapshots'].append({'path': str(legacy), 'backup': None})
    (backup / 'transaction.json').write_text(json.dumps(journal))
    child = Path(journal['children'][0]) / 'transaction.json'
    record = json.loads(child.read_text())
    record.update(config=str(external), config_existed=False)
    child.write_text(json.dumps(record))
    installer.rollback(backup)
    installer.rollback(Path(first['backup']))
    monkeypatch.setattr(Path, 'open', original_open)
    assert external.read_text() == 'user-owned settings'
    assert json.loads(legacy.read_text())[0]['path'] == str(external)


@pytest.mark.parametrize('option', ['--client-config', '--client-format', '--name'])
def test_client_configuration_options_are_rejected(option):
    with pytest.raises(SystemExit) as result:
        installer.main([option, 'external', '--yes'])
    assert result.value.code == 2
