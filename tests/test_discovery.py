import json
from pathlib import Path

import pytest
from mcp import Client

from godot_mcp import discovery
from godot_mcp.discovery import EditorDirectory
from godot_mcp.server import create_server
from godot_mcp.version import PRODUCT_VERSION, PROTOCOL_VERSION


class FakeBridge:
    instances = {}
    endpoints = {}
    calls = {}

    def __init__(self, project: Path):
        self.project = project.resolve()
        self.calls = FakeBridge.calls.setdefault(self.project, [])
        self._endpoint = FakeBridge.endpoints.get(self.project, {})
        FakeBridge.instances[self.project] = self

    def endpoint(self):
        return self._endpoint

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        return {
            "project": str(self.project),
            "engine": {"major": 4, "minor": 7, "patch": 2},
            "version": PRODUCT_VERSION,
            "protocol": PROTOCOL_VERSION,
        }


def register(home: Path, project: Path, *, epoch="epoch", pid=1234):
    (home / "editors").mkdir(parents=True, exist_ok=True)
    (home / "editors" / f"{project.name}.json").write_text(
        json.dumps({"project": str(project), "epoch": epoch}), encoding="utf-8"
    )
    bridge = FakeBridge(project)
    bridge._endpoint = {"project": str(project), "epoch": epoch, "pid": pid, "version": PRODUCT_VERSION}
    FakeBridge.endpoints[bridge.project] = bridge._endpoint
    return bridge


@pytest.fixture
def fake_directory(monkeypatch):
    FakeBridge.instances.clear()
    FakeBridge.endpoints.clear()
    FakeBridge.calls.clear()
    monkeypatch.setattr(discovery, "EditorBridge", FakeBridge)
    monkeypatch.setattr(discovery.psutil, "pid_exists", lambda pid: pid == 1234)


async def call_tool(server, name, arguments=None):
    async with Client(server) as client:
        return await client.call_tool(name, arguments or {})


@pytest.mark.asyncio
async def test_guide_is_available_without_a_project_and_matches_published_sections(tmp_path):
    async with Client(create_server(home=tmp_path / "empty-home")) as client:
        tools = (await client.list_tools()).tools
        guide = next(tool for tool in tools if tool.name == "get_guide")
        assert set(guide.input_schema["properties"]) == {"section", "tool"}
        sections = guide.input_schema["properties"]["section"]["enum"]
        index = await client.call_tool("get_guide", {})
        assert not index.is_error
        for section in sections:
            assert f"`{section}`" in index.content[0].text
            result = await client.call_tool("get_guide", {"section": section})
            assert not result.is_error
            assert result.structured_content is None
            assert len(result.content) == 1 and result.content[0].type == "text"
            assert f"Section: {section}" in result.content[0].text
        assert "`create_nodes`" in result.content[0].text
        from jsonschema import Draft202012Validator

        from godot_mcp.catalog import SPECS
        from godot_mcp.tool_examples import EXAMPLES
        assert set(EXAMPLES) == set(SPECS)
        for name, example in EXAMPLES.items():
            Draft202012Validator(SPECS[name]["inputSchema"]).validate(example)
        detail = await client.call_tool("get_guide", {"section": "tools", "tool": "create_nodes"})
        assert not detail.is_error and '"parent_key"' in detail.content[0].text
        assert "## Example" in detail.content[0].text and "## Current tool catalog" not in detail.content[0].text
        for arguments in ({"tool": "create_nodes"}, {"section": "tools", "tool": "missing"}, {"section": "development/ui"}, {"section": "../server.py"}, {"project": "/tmp/project"}):
            result = await client.call_tool("get_guide", arguments)
            assert result.is_error
            assert result.structured_content["error"]["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_directory_filters_wrong_epoch_and_dead_pid(tmp_path, fake_directory):
    home = tmp_path / "home"
    good = tmp_path / "good"
    wrong = register(home, tmp_path / "wrong", epoch="current")
    wrong._endpoint["epoch"] = "stale"
    dead = register(home, tmp_path / "dead", pid=9999)
    valid = register(home, good)

    projects = EditorDirectory(home).projects()

    assert [item["project"] for item in projects] == [str(valid.project)]
    assert wrong.project not in FakeBridge.instances or wrong._endpoint["epoch"] != "current"
    assert dead.project in FakeBridge.instances


@pytest.mark.asyncio
async def test_no_projects_reports_discovery_context(tmp_path, fake_directory):
    result = await call_tool(create_server(home=tmp_path / "home"), "get_context")

    assert not result.is_error
    assert result.structured_content["projects"] == []
    assert result.structured_content["selection_required"] is False


@pytest.mark.asyncio
async def test_one_project_is_selected_automatically(tmp_path, fake_directory):
    project = tmp_path / "project"
    bridge = register(tmp_path / "home", project)

    result = await call_tool(create_server(home=tmp_path / "home"), "get_context")

    assert not result.is_error
    assert result.structured_content["project"] == str(project.resolve())
    assert FakeBridge.calls[bridge.project] == [("get_context", {})]


@pytest.mark.asyncio
async def test_multiple_projects_require_explicit_selection(tmp_path, fake_directory):
    home = tmp_path / "home"
    first = register(home, tmp_path / "first")
    second = register(home, tmp_path / "second")
    server = create_server(home=home)

    discovery_result = await call_tool(server, "get_context")
    selected = await call_tool(server, "get_context", {"project": str(second.project)})

    assert not discovery_result.is_error
    assert discovery_result.structured_content["selection_required"] is True
    assert discovery_result.structured_content["project"] is None
    assert not selected.is_error
    assert selected.structured_content["project"] == str(second.project)
    assert FakeBridge.calls[first.project] == []
    assert FakeBridge.calls[second.project] == [("get_context", {})]


@pytest.mark.asyncio
async def test_successful_selection_is_reused_and_closed_selection_errors(tmp_path, fake_directory):
    home = tmp_path / "home"
    project = tmp_path / "project"
    bridge = register(home, project)
    server = create_server(home=home)

    selected = await call_tool(server, "get_context", {"project": str(project)})
    reused = await call_tool(server, "get_context")
    (home / "editors" / f"{project.name}.json").unlink()
    closed = await call_tool(server, "get_context")

    assert not selected.is_error and not reused.is_error
    assert reused.structured_content["project"] == str(project)
    assert FakeBridge.calls[bridge.project] == [("get_context", {}), ("get_context", {})]
    assert closed.is_error
    assert closed.structured_content["error"]["code"] == "PROJECT_CLOSED"
