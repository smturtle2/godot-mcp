import pytest

from godot_mcp import cli
from godot_mcp.bridge import ToolError
from godot_mcp.version import ENGINE_VERSION, PRODUCT_VERSION, PROTOCOL_VERSION


def test_version_prints_product_engine_and_protocol(capsys):
    assert cli.main(["version"]) == 0
    output = capsys.readouterr().out
    assert PRODUCT_VERSION in output
    assert ENGINE_VERSION in output
    assert PROTOCOL_VERSION in output


def test_version_option_alias(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--version"])
    assert exit_info.value.code == 0
    assert PRODUCT_VERSION in capsys.readouterr().out


def test_serve_requires_project_file(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(["serve", "--project", str(tmp_path)])


def test_serve_runs_async_server_for_valid_project(tmp_path, monkeypatch):
    (tmp_path / "project.godot").write_text("[application]\nconfig/name=Test\n")
    called = {}

    async def fake_serve(project):
        called["project"] = project

    monkeypatch.setattr(cli, "serve", fake_serve)
    assert cli.main(["serve", "--project", str(tmp_path)]) == 0
    assert called["project"] == tmp_path.resolve()


def test_check_reports_catalog_and_connection(tmp_path, monkeypatch, capsys):
    (tmp_path / "project.godot").write_text("[application]\nconfig/name=Test\n")

    async def fake_call(self, name, arguments):
        assert name == "get_context"
        assert arguments == {}
        return {"project": str(tmp_path.resolve()), "engine": {"major": 4, "minor": 7, "patch": 2},
                "version": PRODUCT_VERSION, "protocol": PROTOCOL_VERSION}

    monkeypatch.setattr("godot_mcp.bridge.EditorBridge.call", fake_call)
    assert cli.main(["check", "--project", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "43 tools" in output
    assert "Editor connection: OK" in output


def test_check_reports_installation_failure_nonzero(tmp_path, monkeypatch, capsys):
    (tmp_path / "project.godot").write_text("[application]\nconfig/name=Test\n")

    async def fake_call(self, name, arguments):
        raise ToolError("EDITOR_DISCONNECTED", "plugin endpoint is missing")

    monkeypatch.setattr("godot_mcp.bridge.EditorBridge.call", fake_call)
    assert cli.main(["check", "--project", str(tmp_path)]) == 1
    assert "Installation check failed" in capsys.readouterr().err


def test_install_forwards_flags(monkeypatch):
    from godot_mcp import installer
    received = []
    monkeypatch.setattr(installer, "main", lambda args: received.extend(args) or 0)
    assert cli.main(["install", "--yes", "--project", "/example"]) == 0
    assert received == ["--yes", "--project", "/example"]
