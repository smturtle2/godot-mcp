"""Real editor behavior for context patches, current diagnostics and continuations."""
from __future__ import annotations

import os

import pytest
from jsonschema import Draft202012Validator
from mcp import Client

from godot_mcp.catalog import SPECS
from godot_mcp.server import create_server

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real editor")]


def added(sources: dict[str, str]) -> str:
    pieces = ["*** Begin Patch"]
    for uri, source in sources.items():
        pieces += [f"*** Add File: {uri}", *["+" + line for line in source.splitlines()]]
    return "\n".join([*pieces, "*** End Patch"])


async def invoke(client, name, **arguments):
    response = await client.call_tool(name, arguments)
    value = response.structured_content
    if "outputSchema" in SPECS[name]:
        Draft202012Validator(SPECS[name]["outputSchema"]).validate(value)
    return response, value


async def finished(client, value):
    if "operation_id" not in value:
        return value
    response, detail = await invoke(client, "get_operation_result", operation_id=value["operation_id"], wait_ms=60000)
    assert not response.is_error, detail
    assert not detail["pending"], detail
    return detail["result"]


async def test_patch_drafts_search_preview_and_guarded_undo(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        patch = added({
            "res://dependent.gd": 'extends Node\nconst Later = preload("res://later.gd")\nfunc answer() -> int:\n\treturn Later.answer()\n',
            "res://later.gd": "extends RefCounted\nstatic func answer() -> int:\n\treturn 42\n",
        })
        response, preview = await invoke(client, "apply_script_changes", patch=patch, preview=True)
        assert not response.is_error and preview["preview"], preview
        assert not (bridge.project / "later.gd").exists()
        response, missing = await invoke(client, "read_scripts", documents=[{"uri": "res://later.gd"}])
        assert response.is_error and missing["error"]["code"] == "FILE_NOT_FOUND"

        response, receipt = await invoke(client, "apply_script_changes", patch=patch, wait_ms=0)
        assert not response.is_error and receipt["status"] == "pending", receipt
        result = await finished(client, receipt)
        assert result["status"] == "completed", result
        assert {item["state"] for item in result["documents"]} == {"draft"}
        assert all(item["validation"]["state"] == "valid" for item in result["documents"]), result
        assert not (bridge.project / "later.gd").exists()
        _, read = await invoke(client, "read_scripts", documents=[{"uri": "res://later.gd"}, {"uri": "res://dependent.gd"}])
        assert set(read["base_revisions"]) == {"res://later.gd", "res://dependent.gd"}
        _, search = await invoke(client, "find_assets", query="answer", mode="symbol", limit=1)
        assert search["has_more"] and search["matches"][0]["unsaved"], search
        assert search["matches"][0]["revision"] == read["base_revisions"][search["matches"][0]["uri"]]
        _, next_page = await invoke(client, "find_assets", query="answer", mode="symbol", limit=1, offset=search["next_offset"])
        assert next_page["matches"][0]["uri"] != search["matches"][0]["uri"]
        assert next_page["matches"][0]["line"] in {2, 3}, next_page
        response, undo = await invoke(client, "undo_edit", edit_id=result["undo"]["edit_id"])
        assert not response.is_error, undo
        _, missing = await invoke(client, "read_scripts", documents=[{"uri": "res://later.gd"}])
        assert missing["error"]["code"] == "FILE_NOT_FOUND"


def native_editor(project):
    path = project / "addons/godot_mcp/plugin.gd"
    source = path.read_text()
    source = source.replace('func dispatch(method: String, p: Dictionary) -> Dictionary:\n', '''func dispatch(method: String, p: Dictionary) -> Dictionary:
	if method == "_test_user_source":
		var script: Script = load(p.uri)
		EditorInterface.edit_script(script)
		var buffer: TextEdit = documents.store.script_buffer(p.uri)
		buffer.begin_complex_operation()
		buffer.select_all()
		buffer.insert_text_at_caret(p.source)
		buffer.deselect()
		buffer.end_complex_operation()
		return documents.source_info(p.uri)
	if method == "_test_history":
		logs._log_message("An old error that has been repaired", true)
		return {"logged": true}
''')
    path.write_text(source)


@pytest.mark.parametrize("editor", [native_editor], indirect=True)
async def test_patch_merges_native_user_edits_and_rejects_overlap(editor):
    bridge, _ = editor
    uri = "res://shared.gd"
    original = "extends Node\nvar first: int = 1\nvar second: int = 1\n"
    async with Client(create_server(bridge.project, bridge)) as client:
        _, created = await invoke(client, "apply_script_changes", patch=added({uri: original}), save=True, wait_ms=0)
        created = await finished(client, created)
        assert created["status"] == "completed", created
        _, read = await invoke(client, "read_scripts", documents=[{"uri": uri}])
        await bridge.call("_test_user_source", {"uri": uri, "source": original.replace("first: int = 1", "first: int = 2")})
        patch = "*** Begin Patch\n*** Update File: res://shared.gd\n@@\n-var second: int = 1\n+var second: int = 3\n*** End Patch"
        response, changed = await invoke(client, "apply_script_changes", patch=patch, base_revisions=read["base_revisions"], wait_ms=0)
        assert not response.is_error, changed
        changed = await finished(client, changed)
        assert changed["status"] == "completed" and changed["documents"][0]["merged"], changed
        _, current = await invoke(client, "read_scripts", documents=[{"uri": uri}])
        assert "first: int = 2" in current["documents"][0]["source"]
        assert "second: int = 3" in current["documents"][0]["source"]
        assert (bridge.project / "shared.gd").read_text() == original
        overlapping = "*** Begin Patch\n*** Add File: res://must_not_exist.gd\n+extends Node\n*** Update File: res://shared.gd\n@@\n-var first: int = 1\n+var first: int = 9\n*** End Patch"
        response, conflict = await invoke(client, "apply_script_changes", patch=overlapping, base_revisions=read["base_revisions"])
        assert response.is_error and conflict["error"]["code"] == "REVISION_CONFLICT", conflict
        _, absent = await invoke(client, "read_scripts", documents=[{"uri": "res://must_not_exist.gd"}])
        assert absent["error"]["code"] == "FILE_NOT_FOUND"
        await bridge.call("_test_history", {})
        _, diagnostics = await invoke(client, "get_diagnostics", uris=[uri], wait_ms=0)
        diagnostics = await finished(client, diagnostics)
        assert diagnostics["state"] == "valid" and diagnostics["error_count"] == 0, diagnostics
        assert "entries" not in diagnostics
        _, logs = await invoke(client, "get_logs", kinds=["error"])
        assert logs["history"] and not logs["current_verdict"]
        assert any("An old error" in item["message"] for item in logs["entries"]), logs


async def test_bundle_saves_attaches_and_connects_in_phases(editor):
    bridge, _ = editor
    ref = {"scene": "res://main.tscn", "path": "Actor"}
    async with Client(create_server(bridge.project, bridge)) as client:
        await invoke(client, "create_nodes", parent={"scene": "res://main.tscn", "path": "."}, nodes=[{"name": "Actor", "source": {"class": "Node2D"}}])
        _, receipt = await invoke(client, "apply_script_changes", patch=added({"res://actor.gd": "extends Node2D\nvar health: int = 100\nfunc react(value: int) -> void:\n\thealth = value\n"}), save=True, attachments=[{"script": {"uri": "res://actor.gd", "node": ref}}], connections={"connect": [{"from": {"scene": "res://main.tscn", "path": "."}, "signal": "health_changed", "to": ref, "method": "react"}]}, wait_ms=0)
        result = await finished(client, receipt)
        assert result["status"] == "completed", result
        assert result["phases"]["bindings"] == result["phases"]["save_bindings"] == "completed"
        assert len(result["undo"]["steps"]) == 3
        assert 'path="res://actor.gd"' in (bridge.project / "main.tscn").read_text()
        _, attached = await invoke(client, "get_resource", target={"node": {**ref, "property": "script"}}, properties=["source_code"])
        assert attached["uri"] == "res://actor.gd"
        _, again = await invoke(client, "get_operation_result", operation_id=result["operation_id"])
        assert not again["current_resume"]["available"]
        for step in reversed(result["undo"]["steps"]):
            response, undone = await invoke(client, "undo_edit", edit_id=step["edit_id"])
            assert not response.is_error, undone
        assert (bridge.project / "actor.gd").exists()
