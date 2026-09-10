import asyncio
import json
from pathlib import Path

import pytest
from websockets.asyncio.server import serve

from godot_mcp.bridge import EditorBridge, ToolError, validate_values
from godot_mcp.version import PRODUCT_VERSION


def write_endpoint(project: Path, **overrides):
    endpoint = {"project": str(project), "port": 1, "token": "t" * 32, "version": PRODUCT_VERSION}
    endpoint.update(overrides)
    target = project / ".godot-mcp/endpoint.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(endpoint))
    return endpoint


def test_endpoint_validates_project_token_port_and_version(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    bridge = EditorBridge(project)
    write_endpoint(project)
    assert bridge.endpoint()["version"] == PRODUCT_VERSION

    for overrides, code in (
        ({"project": str(tmp_path / "other")}, "PROJECT_MISMATCH"),
        ({"token": "short"}, "INVALID_ENDPOINT"),
        ({"port": 0}, "INVALID_ENDPOINT"),
        ({"version": "v0.0.0_0"}, "VERSION_MISMATCH"),
    ):
        if "project" in overrides:
            endpoint_path = project / ".godot-mcp/endpoint.json"
            endpoint_path.write_text(json.dumps({"project": overrides["project"], "port": 1,
                                                  "token": "t" * 32, "version": PRODUCT_VERSION}))
        else:
            write_endpoint(project, **overrides)
        with pytest.raises(ToolError) as caught:
            bridge.endpoint()
        assert caught.value.code == code


@pytest.mark.asyncio
async def test_call_correlates_request_and_returns_result(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    received = {}

    async def handler(ws):
        received.update(json.loads(await ws.recv()))
        await ws.send(json.dumps({"id": received["id"], "result": {"ok": True}}))

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        write_endpoint(project, port=port)
        result = await EditorBridge(project, timeout=1).call("get_context", {})
    assert result == {"ok": True}
    assert received["token"] == "t" * 32
    assert received["method"] == "get_context"


@pytest.mark.asyncio
async def test_call_propagates_editor_error_and_rejects_wrong_id(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    async def error_handler(ws):
        request = json.loads(await ws.recv())
        await ws.send(json.dumps({"id": request["id"], "error": {
            "code": "EDITOR_BUSY", "message": "editor is busy", "details": {"retry": True}
        }}))

    async with serve(error_handler, "127.0.0.1", 0) as server:
        write_endpoint(project, port=server.sockets[0].getsockname()[1])
        with pytest.raises(ToolError) as caught:
            await EditorBridge(project, timeout=1).call("save_documents", {"uris": ["res://main.tscn"]})
    assert caught.value.code == "EDITOR_BUSY"
    assert caught.value.details == {"retry": True}

    async def wrong_id_handler(ws):
        await ws.recv()
        await ws.send(json.dumps({"id": "wrong", "result": {}}))

    async with serve(wrong_id_handler, "127.0.0.1", 0) as server:
        write_endpoint(project, port=server.sockets[0].getsockname()[1])
        with pytest.raises(ToolError) as caught:
            await EditorBridge(project, timeout=1).call("get_context", {})
    assert caught.value.code == "INVALID_RESPONSE"


@pytest.mark.asyncio
async def test_call_reports_disconnect_and_timeout(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    async def disconnect_handler(ws):
        await ws.recv()
        await ws.close()

    async with serve(disconnect_handler, "127.0.0.1", 0) as server:
        write_endpoint(project, port=server.sockets[0].getsockname()[1])
        with pytest.raises(ToolError) as caught:
            await EditorBridge(project, timeout=1).call("get_context", {})
    assert caught.value.code == "EDITOR_DISCONNECTED"

    async def slow_handler(ws):
        await ws.recv()
        await asyncio.sleep(0.2)

    async with serve(slow_handler, "127.0.0.1", 0) as server:
        write_endpoint(project, port=server.sockets[0].getsockname()[1])
        with pytest.raises(ToolError) as caught:
            await EditorBridge(project, timeout=0.05).call("get_context", {})
    assert caught.value.code == "TIMEOUT"


def test_validate_values_rejects_traversal_nonfinite_and_bad_tagged_values(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(ToolError, match="traversal"):
        validate_values(project, {"uri": "res://../outside.tscn"})
    with pytest.raises(ToolError, match="finite"):
        validate_values(project, {"value": float("inf")})
    with pytest.raises(ToolError, match="Unsupported"):
        validate_values(project, {"value": {"$type": "NoSuchType", "value": 1}})
    with pytest.raises(ToolError, match="numeric"):
        validate_values(project, {"value": {"$type": "Vector2", "x": 1}})
    with pytest.raises(ToolError, match="Color space"):
        validate_values(project, {"value": {"$type": "Color", "r": 1, "g": 1, "b": 1, "a": 1,
                                              "space": "display-p3"}})
