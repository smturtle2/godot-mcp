import subprocess
import sys

from godot_mcp import installer


class NoPrompt:
    def isatty(self):
        return False

    def readline(self):
        raise AssertionError("installer must not prompt in default mode")


def test_default_install_is_noninteractive_and_uses_defaults(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    executable = tmp_path / "environment/bin/godot-mcp"
    executable.parent.mkdir(parents=True)
    executable.write_text("server")
    executable.with_name("godot-mcp-launcher").write_text("launcher")
    monkeypatch.setattr(installer, "default_home", lambda: home)
    monkeypatch.setattr(installer, "prepare_environment", lambda source, target, repair=False: (executable, tmp_path / "version"))
    seen = {}

    def global_install(active, target, project=None):
        seen.update(active=active, home=target, project=project)
        return {"backup": str(target / "backup")}

    monkeypatch.setattr(installer, "install_global", global_install)
    monkeypatch.setattr("godot_mcp.command_path.register_path", lambda directory: "PATH configured")
    monkeypatch.setattr(sys, "stdin", NoPrompt())
    assert installer.main([]) == 0
    output = capsys.readouterr().out
    assert "connect" in output and "godot-mcp init" in output
    assert seen["home"] == home.resolve() and seen["project"] is None
    assert "\x1b" not in output


def test_explicit_project_and_home_options_are_retained_without_yes(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.godot").write_text("config_version=5\n")
    home = tmp_path / "home"
    executable = tmp_path / "server"
    executable.write_text("server")
    monkeypatch.setattr(installer, "prepare_environment", lambda source, target, repair=False: (executable, tmp_path / "version"))
    seen = {}

    def global_install(active, target, linked=None):
        seen.update(active=active, home=target, project=linked)
        return {"backup": str(target / "backup")}

    monkeypatch.setattr(installer, "install_global", global_install)
    monkeypatch.setattr("godot_mcp.command_path.register_path", lambda directory: "PATH configured")
    assert installer.main(["--project", str(project), "--home", str(home), "--no-modify-path"]) == 0
    assert seen["project"] == project.resolve() and seen["home"] == home.resolve()


def test_prepare_failure_reports_actionable_stderr(tmp_path, monkeypatch, capsys):
    failure = subprocess.CalledProcessError(1, ["uv", "sync"], stderr="uv sync failed: lock is stale")
    monkeypatch.setattr(installer, "prepare_environment", lambda *args, **kwargs: (_ for _ in ()).throw(failure))
    assert installer.main(["--home", str(tmp_path / "home"), "--no-modify-path"]) == 1
    assert "uv sync failed" in capsys.readouterr().err
