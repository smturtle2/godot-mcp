"""Verify snapshot queries against live persistence and editor undo state."""
from __future__ import annotations

import os

import pytest
from jsonschema import Draft202012Validator
from mcp import Client

from godot_mcp.catalog import SPECS
from godot_mcp.server import create_server

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real editor")]


def prepare_counter(project):
    plugin = project / "addons/godot_mcp/plugin.gd"
    source = plugin.read_text().replace("var busy: bool = false", "var document_dispatches: int = 0\nvar busy: bool = false")
    source = source.replace("func dispatch(method: String, p: Dictionary) -> Dictionary:\n",
                            'func dispatch(method: String, p: Dictionary) -> Dictionary:\n\tif method == "_test_dispatches": return {"count": document_dispatches}\n\tif method in ["_apply_source_plan", "save_documents"]: document_dispatches += 1\n')
    plugin.write_text(source)


@pytest.mark.parametrize("editor", [prepare_counter], indirect=True)
async def test_query_never_reexecutes_and_keeps_snapshot_separate_from_current_undo(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        async def call(name, **arguments):
            response = await client.call_tool(name, arguments)
            assert not response.is_error, response.structured_content
            if "outputSchema" in SPECS[name]:
                Draft202012Validator(SPECS[name]["outputSchema"]).validate(response.structured_content)
            return response.structured_content

        before = await call("read_scripts", documents=[{"uri": "res://main.gd"}])
        source = before["documents"][0]["source"]
        patch = "*** Begin Patch\n*** Update File: res://main.gd\n@@\n extends Node2D\n+# receipt query\n*** End Patch"
        receipt = await call("apply_script_changes", patch=patch, base_revisions=before["base_revisions"], wait_ms=0)
        assert receipt["status"] == "pending"
        assert receipt["operation_id"]
        operation_id = receipt["operation_id"]
        edit_id = receipt["undo"]["edit_id"]
        assert edit_id != operation_id
        first = await call("get_operation_result", operation_id=operation_id, wait_ms=60000)
        assert first["snapshot"] and not first["pending"]
        assert first["result"]["documents"][0]["state"] == "modified"
        assert first["current_undo"] == {"edit_id": edit_id, "available": True}
        assert await call("get_operation_result", operation_id=operation_id) == first
        assert await bridge.call("_test_dispatches", {}) == {"count": 1}
        saved = await call("save_documents", uris=["res://main.gd"])
        assert saved["operation_id"]
        assert not (await call("read_scripts", documents=[{"uri": "res://main.gd"}]))["documents"][0]["unsaved"]
        assert (await call("get_operation_result", operation_id=operation_id))["result"] == first["result"]
        assert await bridge.call("_test_dispatches", {}) == {"count": 2}
        await call("undo_edit", edit_id=edit_id)
        after = await call("get_operation_result", operation_id=operation_id, wait_ms=60000)
        assert not after["current_undo"]["available"] and after["current_undo"]["reason"]
        assert after["result"] == first["result"] and after["recorded_at_usec"] == first["recorded_at_usec"]
        assert await bridge.call("_test_dispatches", {}) == {"count": 2}
        assert (await call("read_scripts", documents=[{"uri": "res://main.gd"}]))["documents"][0]["source"] == source
        assert "# receipt query" in (bridge.project / "main.gd").read_text()
