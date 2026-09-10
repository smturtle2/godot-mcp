import json
import sys

import pytest

from godot_mcp import launcher


@pytest.fixture(autouse=True)
def isolated_home_environment(monkeypatch):
    monkeypatch.setenv("GODOT_MCP_HOME", "")


def setup(tmp_path):
    location = tmp_path / "bin"
    location.mkdir()
    wrapper = location / "godot-mcp"
    wrapper.write_text("wrapper")
    home = tmp_path / "home"
    home.mkdir()
    executable = tmp_path / "active-server"
    executable.write_text("server")
    (location / "godot-mcp-launcher.json").write_text(json.dumps({"schema_version": 1, "home": str(home)}))
    (home / "active.json").write_text(json.dumps({"executable": str(executable)}))
    return wrapper, executable, home


def test_launcher_routes_active_executable_and_adds_default_home(monkeypatch, tmp_path):
    wrapper, executable, home = setup(tmp_path)
    monkeypatch.setattr(sys, "argv", [str(wrapper), "connect"])
    called = {}
    monkeypatch.setattr(launcher.os, "execv", lambda path, args: called.update(path=path, args=args))
    assert launcher.main() == 0
    assert called == {"path": str(executable), "args": [str(executable), "connect", "--home", str(home)]}
    assert launcher.os.environ["GODOT_MCP_HOME"] == str(home)


def test_launcher_preserves_explicit_home_and_rejects_self_or_missing(tmp_path, monkeypatch, capsys):
    wrapper, executable, home = setup(tmp_path)
    monkeypatch.setattr(sys, "argv", [str(wrapper), "connect", "--home=/custom"])
    called = {}
    monkeypatch.setattr(launcher.os, "execv", lambda path, args: called.update(path=path, args=args))
    assert launcher.main() == 0 and called["args"][-1] == "--home=/custom"
    (home / "active.json").write_text(json.dumps({"executable": str(wrapper)}))
    assert launcher.main() == 1
    (home / "active.json").write_text(json.dumps({"executable": str(tmp_path / "missing")}))
    assert launcher.main() == 1
    assert "Godot MCP launcher:" in capsys.readouterr().err


def test_launcher_rejects_recursive_or_invalid_descriptor(tmp_path, monkeypatch):
    wrapper, executable, home = setup(tmp_path)
    (wrapper.parent / "godot-mcp-launcher.json").write_text(json.dumps({"schema_version": 1, "home": str(home)}))
    (home / "active.json").write_text(json.dumps({"executable": str(wrapper)}))
    monkeypatch.setattr(sys, "argv", [str(wrapper), "connect"])
    monkeypatch.setattr(launcher.os, "execv", lambda *_: pytest.fail("must reject recursive launcher"))
    assert launcher.main() == 1
