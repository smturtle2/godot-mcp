import json
import os
import tomllib

import pytest

from godot_mcp.client_config import register_client, register_global_client


def test_json_preserves_unrelated_and_updates_same_project(tmp_path):
    path = tmp_path / "client.json"
    original = {"theme": "dark", "mcpServers": {"other": {"command": "x", "args": []}}}
    path.write_text(json.dumps(original))
    result = register_client(path, "godot", tmp_path / "bin" / "server", tmp_path / "game")
    data = json.loads(path.read_text())
    assert data["theme"] == "dark" and data["mcpServers"]["other"] == original["mcpServers"]["other"]
    assert result["server_key"] == "godot"
    assert data["mcpServers"]["godot"]["args"] == ["serve", "--project", str((tmp_path / "game").resolve())]
    assert result["backup_path"] and __import__("pathlib").Path(result["backup_path"]).exists()
    old = path.read_text()
    result2 = register_client(path, "godot", tmp_path / "bin" / "new", tmp_path / "game")
    assert result2["server_key"] == "godot" and result2["backup_path"]
    assert json.loads(path.read_text())["mcpServers"]["godot"]["command"].endswith("new")
    assert old != path.read_text()


def test_json_same_name_different_projects_get_stable_suffix(tmp_path):
    path = tmp_path / "client.json"
    first = tmp_path / "one"
    second = tmp_path / "two"
    register_client(path, "godot", tmp_path / "server", first)
    result = register_client(path, "godot", tmp_path / "server", second)
    assert result["server_key"].startswith("godot-")
    assert len(json.loads(path.read_text())["mcpServers"]) == 2


def test_vscode_and_codex_shapes_preserve_registrations(tmp_path):
    vscode = tmp_path / "vscode.json"
    vscode.write_text('{"editor": {"font": 12}, "servers": {"other": {"type": "stdio"}}}')
    register_client(vscode, "godot", tmp_path / "server", tmp_path / "game", "vscode")
    data = json.loads(vscode.read_text())
    assert data["editor"] == {"font": 12} and data["servers"]["other"] == {"type": "stdio"}
    assert data["servers"]["godot"]["type"] == "stdio"

    codex = tmp_path / "config.toml"
    codex.write_text('theme = "dark"\n\n[mcp_servers.other]\ncommand = "other"\nargs = []\n')
    register_client(codex, "godot", tmp_path / "server", tmp_path / "game", "codex")
    parsed = tomllib.loads(codex.read_text())
    assert parsed["theme"] == "dark" and parsed["mcp_servers"]["other"]["command"] == "other"
    assert parsed["mcp_servers"]["godot"]["args"][0] == "serve"


def test_toml_single_quoted_heading_inline_fields_and_unicode_path(tmp_path):
    path = tmp_path / "config.toml"
    project = tmp_path / "게임 프로젝트"
    path.write_text(f"title = 'keep'\n[mcp_servers]\n\n[mcp_servers.'godot']\ncommand = 'old'\nargs = ['serve', '--project', {json.dumps(str(project.resolve()))}]\nenv = {{ TOKEN = 'secret' }}\n")
    result = register_client(path, "godot", tmp_path / "server", project, "codex")
    parsed = tomllib.loads(path.read_text())
    assert result["server_key"] == "godot"
    assert parsed["title"] == "keep"
    assert parsed["mcp_servers"]["godot"]["env"] == {"TOKEN": "secret"}
    assert parsed["mcp_servers"]["godot"]["args"][-1] == str(project.resolve())


def test_backup_and_atomic_replacement_keep_restrictive_mode(tmp_path):
    path = tmp_path / "client.json"
    path.write_text('{"mcpServers": {}}')
    path.chmod(0o640)
    result = register_client(path, "godot", tmp_path / "server", tmp_path / "game")
    assert os.stat(path).st_mode & 0o7777 == 0o640
    assert os.stat(result["backup_path"]).st_mode & 0o7777 == 0o640


def test_name_must_be_safe_and_nonempty(tmp_path):
    with pytest.raises(ValueError):
        register_client(tmp_path / "config.json", "", tmp_path / "server", tmp_path / "game")
    with pytest.raises(ValueError):
        register_client(tmp_path / "config.json", "bad/name", tmp_path / "server", tmp_path / "game")


def test_global_registration_is_project_independent_and_preserves_env(tmp_path):
    path = tmp_path / "client.json"
    path.write_text(json.dumps({"mcpServers": {"godot-mcp": {"command": "/usr/bin/godot-mcp", "args": ["serve", "--project", "/old"], "env": {"TOKEN": "x"}}}}))
    home = tmp_path / "shared"
    first = register_global_client(path, "godot-mcp", tmp_path / "server", home)
    second = register_global_client(path, "godot-mcp", tmp_path / "server", home)
    data = json.loads(path.read_text())["mcpServers"]
    assert first["server_key"] == second["server_key"] == "godot-mcp"
    assert len(data) == 1 and data["godot-mcp"]["args"] == ["connect", "--home", str(home.resolve())]
    assert data["godot-mcp"]["env"] == {"TOKEN": "x"}


def test_global_different_home_does_not_overwrite_unrelated_same_name(tmp_path):
    path = tmp_path / "client.json"
    register_global_client(path, "godot-mcp", tmp_path / "server", tmp_path / "one")
    result = register_global_client(path, "godot-mcp", tmp_path / "server", tmp_path / "two")
    assert result["server_key"].startswith("godot-mcp-")
    assert len(json.loads(path.read_text())["mcpServers"]) == 2


def test_invalid_config_is_non_mutating(tmp_path):
    for suffix, fmt, text in ((".json", "json", "{bad"), (".toml", "codex", "[broken")):
        path = tmp_path / f"config{suffix}"
        path.write_text(text)
        with pytest.raises(ValueError):
            register_client(path, "godot", tmp_path / "server", tmp_path / "game", fmt)
        assert path.read_text() == text
        assert list(tmp_path.glob(f"config{suffix}.bak.*")) == []
