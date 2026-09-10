import importlib
import os
import subprocess

import pytest

bootstrap = importlib.import_module("godot_mcp.bootstrap")


def test_autodetect_success_never_prompts(monkeypatch):
    monkeypatch.setattr(bootstrap, "godot_candidates", lambda: ["first"])
    monkeypatch.setattr(bootstrap, "probe_godot", lambda command, expected: (command, "4.7.2"))
    def prompt():
        pytest.fail("prompt must not be called")
    assert bootstrap.resolve_godot(expected="4.7.2", prompt=prompt) == ("first", "4.7.2")


def test_failed_candidate_continues_to_next(monkeypatch):
    monkeypatch.setattr(bootstrap, "godot_candidates", lambda: ["bad", "good"])
    calls = []

    def probe(command, expected):
        calls.append(command)
        if command == "bad":
            raise ValueError("incompatible")
        return command, "4.7.2"

    monkeypatch.setattr(bootstrap, "probe_godot", probe)
    assert bootstrap.resolve_godot(interactive=False) == ("good", "4.7.2")
    assert calls == ["bad", "good"]


def test_failed_detection_prompts_once_per_invalid_attempt_then_valid(monkeypatch):
    monkeypatch.setattr(bootstrap, "godot_candidates", lambda: ["bad"])
    responses = iter(["still-bad", "valid"])
    calls = []

    def probe(command, expected):
        calls.append(command)
        if command != "valid":
            raise ValueError("bad candidate")
        return command, "4.7.2"

    monkeypatch.setattr(bootstrap, "probe_godot", probe)
    assert bootstrap.resolve_godot(prompt=lambda: next(responses)) == ("valid", "4.7.2")
    assert calls == ["bad", "still-bad", "valid"]


def test_noninteractive_failure_does_not_prompt(monkeypatch):
    monkeypatch.setattr(bootstrap, "godot_candidates", lambda: ["bad"])
    monkeypatch.setattr(bootstrap, "probe_godot", lambda *_: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(ValueError, match="Could not find"):
        bootstrap.resolve_godot(interactive=False, prompt=lambda: pytest.fail("no prompt"))


def test_explicit_override_is_used_exclusively(monkeypatch):
    monkeypatch.setattr(bootstrap, "godot_candidates", lambda: pytest.fail("auto detect must not run"))
    monkeypatch.setattr(bootstrap, "probe_godot", lambda command, expected: (command, expected))
    assert bootstrap.resolve_godot("/custom/Godot", expected="4.7.2", interactive=False) == ("/custom/Godot", "4.7.2")


def test_probe_normalizes_quoted_path_app_bundle_and_rejects_incompatible(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="4.7.2.stable.arch\n", stderr="")

    monkeypatch.setattr(bootstrap.subprocess, "run", fake_run)
    monkeypatch.setattr(bootstrap.shutil, "which", lambda value: None)
    executable, version = bootstrap.probe_godot('"/Applications/Godot.app"', "4.7.2")
    assert executable.endswith("Godot.app/Contents/MacOS/Godot")
    assert seen["command"][0].endswith("Contents/MacOS/Godot") and version == "4.7.2"
    with pytest.raises(ValueError, match="required"):
        bootstrap.probe_godot("Godot", "4.8.0")


def test_installation_environment_strips_only_nested_runtime_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("VIRTUAL_ENV", "/virtual")
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/old")
    monkeypatch.setenv("PYTHONPATH", "/source")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy")
    monkeypatch.setenv("UV_CACHE_DIR", "/cache")
    before = dict(os.environ)
    result = bootstrap.installation_environment(tmp_path / "environment")
    assert "VIRTUAL_ENV" not in result and result["UV_PROJECT_ENVIRONMENT"] == str(tmp_path / "environment")
    assert "PYTHONPATH" not in result and result["HTTPS_PROXY"] == "http://proxy" and result["UV_CACHE_DIR"] == "/cache"
    assert dict(os.environ) == before


def test_local_source_bootstrap_uses_frozen_copy_mode_and_clean_environment(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    called = {}
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)

    def fake_call(command, **kwargs):
        called["command"], called["env"] = command, kwargs["env"]
        return 0

    monkeypatch.setattr(bootstrap.subprocess, "call", fake_call)
    monkeypatch.setenv("PYTHONPATH", "/must-strip")
    assert bootstrap.main(["--source", str(source), "--yes", "--project", "/tmp/project"]) == 0
    assert "--frozen" in called["command"] and "--link-mode" in called["command"] and "copy" in called["command"]
    assert "PYTHONPATH" not in called["env"]
