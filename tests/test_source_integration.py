"""Source identity, coherent diagnostics, batch state, and persistence on real Godot."""
from __future__ import annotations

import os

import pytest
from jsonschema import Draft202012Validator
from mcp import Client

from godot_mcp.catalog import SPECS
from godot_mcp.server import create_server

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real editor")]


def node(path="."):
    return {"scene": "res://main.tscn", "path": path}


async def invoke(client, name, **arguments):
    response = await client.call_tool(name, arguments)
    result = response.structured_content
    if "outputSchema" in SPECS[name]:
        Draft202012Validator(SPECS[name]["outputSchema"]).validate(result)
    return response, result


async def operation_result(client, receipt):
    _, detail = await invoke(client, "get_operation_result", operation_id=receipt["operation_id"])
    return detail["result"]


async def test_source_identity_partial_results_and_save_undo(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        await invoke(client, "create_nodes", parent=node(), nodes=[
            {"name": "Good", "source": {"class": "Node2D"}}, {"name": "Bad", "source": {"class": "Node"}},
        ])
        response, created = await invoke(client, "create_script", uri="res://identity.gd", source="extends Node2D\nvar answer: int = 1\n", attach_to=[node("Good"), node("Bad")])
        created_full = await operation_result(client, created)
        assert response.is_error and created["status"] == "partial", created
        document = created_full["documents"][0]
        assert document["state"] == "saved" and document["effect"] == "created"
        assert document["save"]["state"] == "saved"
        assert created["attachments"] == [node("Good")]
        assert created["failures"][0]["code"] == "INCOMPATIBLE_BASE"
        assert created["undo"]["scope"] == ["attachments"]
        assert created["undo"]["edit_id"]
        _, attached = await invoke(client, "get_resource", target={"node": {**node("Good"), "property": "script"}}, properties=["source_code"])
        assert attached["uri"] == "res://identity.gd"
        # Breakpoint setup opens the actual ScriptEditor buffer, exercising its
        # unsaved text rather than only the store/resource representation.
        await invoke(client, "set_breakpoints", breakpoints=[{"uri": "res://identity.gd", "line": 2}])
        _, before = await invoke(client, "read_script", uri="res://identity.gd")
        assert before["buffer"] == "editor", before
        response, changed = await invoke(client, "edit_script", change={"replace": {"uri": "res://identity.gd", "if_revision": before["revision"], "source": "extends Node2D\nvar answer: int = 2\n"}})
        changed_full = await operation_result(client, changed)
        assert not response.is_error and changed_full["documents"][0]["validation"]["state"] == "valid", changed_full
        assert changed_full["documents"][0]["state"] == "modified"
        _, attached = await invoke(client, "get_resource", target={"node": {**node("Good"), "property": "script"}}, properties=["source_code"])
        assert "= 2" in attached["properties"]["source_code"]
        assert "= 1" in (bridge.project / "identity.gd").read_text()
        response, saved = await invoke(client, "save_documents", uris=["res://main.tscn", "res://missing.gd"])
        assert response.is_error and saved["status"] == "partial"
        saved_full = await operation_result(client, saved)
        assert saved_full["documents"][0]["save"]["state"] == "saved"
        assert saved_full["documents"][1]["save"]["state"] == "failed"
        assert saved_full["documents"][1]["uri"] == "res://missing.gd"
        assert saved_full["documents"][2]["save"] == {"state": "saved", "requested": False}, saved_full
        assert saved_full["documents"][2]["uri"] == "res://identity.gd"
        scene_text = (bridge.project / "main.tscn").read_text()
        assert 'path="res://identity.gd"' in scene_text and 'type="GDScript"' not in scene_text
        await invoke(client, "undo_edit", edit_id=changed["undo"]["edit_id"])
        _, undone = await invoke(client, "read_script", uri="res://identity.gd")
        assert "= 1" in undone["source"] and undone["unsaved"]
        assert "= 2" in (bridge.project / "identity.gd").read_text()
        response, invalid = await invoke(client, "create_script", uri="res://invalid.gd", source="extends Node\nfunc broken(:\n", attach_to=[node("Bad")])
        invalid_full = await operation_result(client, invalid)
        assert response.is_error and invalid["status"] == "partial"
        assert invalid_full["documents"][0]["save"]["state"] == "saved"
        assert invalid_full["documents"][0]["validation"]["state"] == "invalid" and not invalid_full.get("attachments")
        assert (bridge.project / "invalid.gd").exists()
        response, again = await invoke(client, "create_script", uri="res://invalid.gd", source="extends Node\n")
        assert response.is_error and again["error"]["code"] == "ALREADY_EXISTS"
        response, shader = await invoke(client, "create_script", uri="res://bad.gdshader", source="shader_type canvas_item;\nvoid fragment() { COLOR = unknown_symbol; }\n")
        shader_full = await operation_result(client, shader)
        assert response.is_error and shader_full["documents"][0]["validation"]["state"] == "invalid", shader_full
        response, diagnostics = await invoke(client, "get_diagnostics", uris=["res://bad.gdshader"])
        assert not response.is_error and diagnostics["sources"][0]["valid"] is False
        assert diagnostics["entries_are_history"] is True


async def test_batch_dependencies_drafts_and_preflight(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        changes = [
            {"create": {"uri": "res://dependent.gd", "source": 'extends Node\nconst Later = preload("res://later.gd")\nfunc value() -> int:\n\treturn Later.answer()\n'}},
            {"create": {"uri": "res://later.gd", "source": "extends RefCounted\nstatic func answer() -> int:\n\treturn 42\n"}},
        ]
        response, batch = await invoke(client, "apply_script_changes", changes=changes)
        batch_full = await operation_result(client, batch)
        assert not response.is_error, batch
        assert all(doc["validation"]["state"] == "valid" for doc in batch_full["documents"]), batch_full
        assert {doc["state"] for doc in batch_full["documents"]} == {"draft"}
        assert {doc["live_reload"] for doc in batch_full["documents"]} == {"deferred"}
        assert not (bridge.project / "dependent.gd").exists() and not (bridge.project / "later.gd").exists()
        assert batch["undo"]["scope"] == ["live_sources"]
        response, undone = await invoke(client, "undo_edit", edit_id=batch["undo"]["edit_id"])
        assert not response.is_error, undone
        response, gone = await invoke(client, "read_script", uri="res://later.gd")
        assert response.is_error and gone["error"]["code"] == "FILE_NOT_FOUND", gone
        response, batch = await invoke(client, "apply_script_changes", changes=changes, save=True)
        batch_full = await operation_result(client, batch)
        assert all(doc["validation"]["state"] == "valid" for doc in batch_full["documents"]), batch_full
        assert all(doc["save"]["state"] == "saved" for doc in batch_full["documents"])
        assert all((bridge.project / name).exists() for name in ["dependent.gd", "later.gd"])
        _, current = await invoke(client, "read_script", uri="res://later.gd")
        response, invalid_edit = await invoke(client, "apply_script_changes", changes=[
            {"create": {"uri": "res://must_not_exist.gd", "source": "extends Node\n"}},
            {"replace": {"uri": "res://later.gd", "if_revision": "stale", "source": "extends Node\n"}},
        ])
        assert response.is_error and invalid_edit["error"]["code"] == "REVISION_CONFLICT"
        response, absent = await invoke(client, "read_script", uri="res://must_not_exist.gd")
        assert response.is_error and absent["error"]["code"] == "FILE_NOT_FOUND"
        # A dependency-only unsaved API change invalidates a formerly valid dependent.
        await invoke(client, "edit_script", change={"replace": {"uri": "res://later.gd", "if_revision": current["revision"], "source": "extends RefCounted\nstatic func renamed() -> int:\n\treturn 42\n"}})
        response, fresh = await invoke(client, "get_diagnostics", uris=["res://dependent.gd"])
        assert not response.is_error and fresh["sources"][0]["valid"] is False, fresh
        assert "answer" in str(fresh["sources"][0]["entries"])
        assert "answer" in (bridge.project / "later.gd").read_text()
        _, current = await invoke(client, "read_script", uri="res://later.gd")
        await invoke(client, "edit_script", change={"replace": {"uri": "res://later.gd", "if_revision": current["revision"], "source": changes[1]["create"]["source"]}})
        _, fresh = await invoke(client, "get_diagnostics", uris=["res://dependent.gd"])
        assert fresh["sources"][0]["valid"] is True, fresh

async def test_property_planner_rejects_incompatible_script_and_retries_attachment(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        await invoke(client, "create_nodes", parent=node(), nodes=[{"name": "Target", "source": {"class": "Node"}}])
        response, created = await invoke(
            client,
            "create_script",
            uri="res://repairable.gd",
            source="extends Node2D\n",
            attach_to=[node("Target")],
        )
        assert response.is_error and created["status"] == "partial"
        retry = created["failures"][0]["recovery"]
        assert retry["tool"] == "update_nodes"
        assert retry["arguments"]["changes"][0]["node"] == node("Target")
        assert retry["arguments"]["changes"][0]["set"]["script"]["$type"] == "Resource"

        response, rejected = await invoke(client, "update_nodes", **retry["arguments"])
        assert response.is_error and rejected["error"]["code"] == "INVALID_PROPERTY"
        _, before = await invoke(client, "get_scene", scene="res://main.tscn", path="Target", properties=["script"])
        assert before["root"]["properties"]["script"] is None

        _, current = await invoke(client, "read_script", uri="res://repairable.gd")
        response, repaired = await invoke(
            client,
            "edit_script",
            change={"replace": {"uri": "res://repairable.gd", "if_revision": current["revision"], "source": "extends Node\n"}},
        )
        assert not response.is_error and repaired["documents"][0]["validation"]["state"] == "valid"
        await invoke(client, "get_diagnostics", uris=["res://repairable.gd"])
        await invoke(client, "save_documents", uris=["res://repairable.gd"])
        response, attached = await invoke(client, "update_nodes", **retry["arguments"])
        assert not response.is_error, attached
        _, after = await invoke(client, "get_resource", target={"node": {**node("Target"), "property": "script"}}, properties=["source_code"])
        assert after["uri"] == "res://repairable.gd"


async def test_shader_material_attachment_retry_after_source_repair(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        _, material = await invoke(client, "create_resource", **{"class": "ShaderMaterial"})
        material_uri = material["resource"]["uri"]
        response, created = await invoke(
            client,
            "create_script",
            uri="res://repairable.gdshader",
            source="shader_type canvas_item;\nvoid fragment() { COLOR = unknown_symbol; }\n",
            material={"uri": material_uri},
        )
        created_full = await operation_result(client, created)
        assert response.is_error and created_full["documents"][0]["save"]["state"] == "saved"
        assert (bridge.project / "repairable.gdshader").exists()
        retry = created["failures"][0]["recovery"]
        assert retry["tool"] == "update_resource"
        assert retry["arguments"]["target"] == {"shared": {"uri": material_uri}}
        Draft202012Validator(SPECS["update_resource"]["inputSchema"]).validate(retry["arguments"])

        _, current = await invoke(client, "read_script", uri="res://repairable.gdshader")
        response, repaired = await invoke(
            client,
            "edit_script",
            change={"replace": {"uri": "res://repairable.gdshader", "if_revision": current["revision"], "source": "shader_type canvas_item;\nvoid fragment() { COLOR = vec4(1.0); }\n"}},
        )
        assert not response.is_error and repaired["documents"][0]["validation"]["state"] == "valid"
        response, attached = await invoke(client, retry["tool"], **retry["arguments"])
        assert not response.is_error, attached
        _, material_after = await invoke(client, "get_resource", target={"uri": material_uri}, properties=["shader"])
        assert material_after["properties"]["shader"]["uri"] == "res://repairable.gdshader"


async def test_document_detail_save_as_attempts(editor):
    bridge, _ = editor
    uri = "res://format_modes.gd"
    moved_uri = "res://format_modes_moved.gd"
    source = "extends Node\nvar number: int = 1\n"
    async with Client(create_server(bridge.project, bridge)) as client:
        response = await client.call_tool("create_script", {"uri": uri, "source": source})
        assert not response.is_error
        created = response.structured_content
        created = await operation_result(client, created)
        document = created["documents"][0]
        assert {"disk_revision", "base_disk_revision", "baseline_known"} <= document.keys()
        assert document["validation"]["state"] == "valid"
        assert "revision" not in document["validation"]

        response = await client.call_tool("save_documents", {"uris": [uri], "save_as": {uri: moved_uri}})
        assert not response.is_error, response.structured_content
        moved = (await operation_result(client, response.structured_content))["documents"]
        assert len(moved) == 1 and moved[0]["uri"] == moved_uri
        assert moved[0]["save"]["state"] == "saved"
        assert moved[0]["save"]["previous_uri"] == uri

        _, current = await invoke(client, "read_script", uri=moved_uri)
        _, edited = await invoke(client, "edit_script", change={"replace": {"uri": moved_uri, "if_revision": current["revision"], "source": "extends Node\nvar number: int = 2\n"}})
        response = await client.call_tool("save_documents", {"uris": [moved_uri, moved_uri]})
        assert not response.is_error, response.structured_content
        repeated = (await operation_result(client, response.structured_content))["documents"]
        assert len(repeated) == 1
        assert [attempt["index"] for attempt in repeated[0]["save"]["attempts"]] == [0, 1]
