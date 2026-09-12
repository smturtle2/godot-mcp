import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from godot_mcp import installer
from godot_mcp.bridge import ToolError
from godot_mcp.server import create_server
from godot_mcp.version import PRODUCT_VERSION


def make_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.godot").write_text("config_version=5\n")
    return project


def make_home(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    executable = tmp_path / "bin" / "godot-mcp"
    executable.parent.mkdir()
    executable.write_text("executable")
    (home).mkdir()
    (home / "active.json").write_text(json.dumps({"executable": str(executable), "version": PRODUCT_VERSION}))
    return home, executable


def test_initialize_project_installs_addon_and_records_link(tmp_path):
    project = make_project(tmp_path)
    home, executable = make_home(tmp_path)
    result = installer.initialize_project(project, home)
    assert result["project"] == str(project.resolve())
    assert Path(result["executable"]).resolve() == executable.resolve()
    assert (project / "addons/godot_mcp/plugin.cfg").is_file()
    assert "res://addons/godot_mcp/plugin.cfg" in (project / "project.godot").read_text()
    link = json.loads((project / ".godot-mcp/install.json").read_text())
    assert link["home"] == str(home.resolve()) and link["version"] == PRODUCT_VERSION


def test_initialize_project_rejects_missing_project_or_mismatched_active_version(tmp_path):
    home, _ = make_home(tmp_path)
    with pytest.raises(ValueError):
        installer.initialize_project(tmp_path / "missing", home)
    project = make_project(tmp_path)
    (home / "active.json").write_text(json.dumps({"executable": "/tmp/server", "version": "v0.0.0_0"}))
    with pytest.raises(ValueError, match="(?:version|differs)"):
        installer.initialize_project(project, home)
    assert not (project / "addons").exists()


def test_install_plugin_requires_absolute_project_and_fixed_server_rejects_other(tmp_path):
    project = make_project(tmp_path)
    home, _ = make_home(tmp_path)
    with pytest.raises(ValueError):
        installer.initialize_project(Path("relative"), home)

    async def exercise():
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            server = create_server(home=home)
            task = asyncio.create_task(server.run(*server_streams, server.create_initialization_options()))
            try:
                async with ClientSession(*client_streams) as client:
                    await client.initialize()
                    result = await client.call_tool("install_plugin", {"project": str(project.resolve())})
                    assert not result.is_error
                    relative = await client.call_tool("install_plugin", {"project": "relative/project"})
                    assert relative.is_error
                    missing = await client.call_tool("install_plugin", {"project": str(tmp_path / "missing")})
                    assert missing.is_error
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def test_fixed_server_rejects_other_project(tmp_path):
    project, other = make_project(tmp_path), tmp_path / "other"
    other.mkdir()
    home, _ = make_home(tmp_path)

    async def exercise():
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            server = create_server(project, home=home)
            task = asyncio.create_task(server.run(*server_streams, server.create_initialization_options()))
            try:
                async with ClientSession(*client_streams) as client:
                    await client.initialize()
                    result = await client.call_tool("install_plugin", {"project": str(other.resolve())})
                    assert result.is_error and result.structured_content["error"]["code"] == "PROJECT_MISMATCH"
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


@pytest.mark.asyncio
async def test_create_project_resumes_after_launch_failure_without_replacing_edits(tmp_path, monkeypatch):
    from godot_mcp import project_setup

    home, _ = make_home(tmp_path)
    project = tmp_path / "new-game"
    connected = False
    launches = []

    class Bridge:
        def __init__(self, *_args, **_kwargs):
            pass

        async def call(self, *_args):
            if not connected:
                raise ToolError("EDITOR_DISCONNECTED", "Not open yet.")
            return {"project": str(project), "active_scene": None}

    async def launch(*args, **kwargs):
        nonlocal connected
        launches.append((args, kwargs))
        if len(launches) == 1:
            raise FileNotFoundError("Editor path is missing")
        connected = True
        return SimpleNamespace(pid=os.getpid())

    monkeypatch.setattr(project_setup, "EditorBridge", Bridge)
    monkeypatch.setattr(project_setup.asyncio, "create_subprocess_exec", launch)
    setup = project_setup.ProjectSetup(home)
    failed = await setup.create(project, 'Game "Name"', "missing-godot", {"DISPLAY": ":explicit"})
    assert launches[0][1]["env"]["DISPLAY"] == ":explicit"
    assert failed["status"] == "partial" and failed["project_created"] and failed["plugin_installed"]
    assert not failed["editor_started"] and failed["failures"][0]["phase"] == "launch"
    content = (project / "project.godot").read_text() + '\n[custom]\nvalue=42\n'
    (project / "project.godot").write_text(content)
    completed = await setup.create(project, "Ignored on retry", "godot", {"DISPLAY": ":explicit"})
    assert completed["status"] == "completed" and completed["connected"]
    assert (project / "project.godot").read_text() == content
    assert launches[-1][0] == ("godot", "--editor", "--path", str(project))
    assert launches[-1][1]["env"]["GODOT_MCP_HOME"] == str(home)
    assert (await setup.create(project))["connected"] and len(launches) == 2
    existing = make_project(tmp_path)
    with pytest.raises(ToolError, match="new or empty"):
        await setup.create(existing)
