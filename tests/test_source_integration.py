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


async def test_source_identity_partial_results_and_save_undo(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        await invoke(client, "create_nodes", parent=node(), nodes=[
            {"name": "Good", "class": "Node2D"}, {"name": "Bad", "class": "Node"},
        ])
        response, created = await invoke(client, "create_script", uri="res://identity.gd", source="extends Node2D\nvar answer: int = 1\n", attach_to=[node("Good"), node("Bad")])
        assert response.is_error and created["status"] == "partial", created
        assert created["saved"] and created["attached"] == [node("Good")]
        assert created["attachment_errors"][0]["code"] == "INCOMPATIBLE_BASE"
        assert created["undo"]["scope"] == ["attachments"]
        _, attached = await invoke(client, "get_resource", target={"node": node("Good"), "property": "script"}, properties=["source_code"])
        assert attached["uri"] == "res://identity.gd"
        # Breakpoint setup opens the actual ScriptEditor buffer, exercising its
        # unsaved text rather than only the store/resource representation.
        await invoke(client, "set_breakpoints", breakpoints=[{"uri": "res://identity.gd", "line": 2}])
        _, before = await invoke(client, "read_script", uri="res://identity.gd")
        assert before["buffer"] == "editor", before
        response, changed = await invoke(client, "edit_script", uri="res://identity.gd", if_revision=before["revision"], source="extends Node2D\nvar answer: int = 2\n")
        assert not response.is_error and changed["diagnostics"]["valid"] is True, changed
        assert changed["saved"] is False and changed["documents"][0]["state"] == "modified"
        _, attached = await invoke(client, "get_resource", target={"node": node("Good"), "property": "script"}, properties=["source_code"])
        assert "= 2" in attached["properties"]["source_code"]
        assert "= 1" in (bridge.project / "identity.gd").read_text()
        response, saved = await invoke(client, "save_documents", uris=["res://main.tscn", "res://missing.gd"])
        assert response.is_error and saved["status"] == "partial"
        assert len(saved["saved"]) == 1 and len(saved["failed"]) == 1
        assert saved["also_saved"] == ["res://identity.gd"], saved
        scene_text = (bridge.project / "main.tscn").read_text()
        assert 'path="res://identity.gd"' in scene_text and 'type="GDScript"' not in scene_text
        await invoke(client, "undo_edit", edit_id=changed["edit_id"])
        _, undone = await invoke(client, "read_script", uri="res://identity.gd")
        assert "= 1" in undone["source"] and undone["unsaved"]
        assert "= 2" in (bridge.project / "identity.gd").read_text()
        response, invalid = await invoke(client, "create_script", uri="res://invalid.gd", source="extends Node\nfunc broken(:\n", attach_to=[node("Bad")])
        assert response.is_error and invalid["status"] == "partial"
        assert invalid["saved"] and invalid["diagnostics"]["valid"] is False and not invalid["attached"]
        assert (bridge.project / "invalid.gd").exists()
        response, again = await invoke(client, "create_script", uri="res://invalid.gd", source="extends Node\n")
        assert response.is_error and again["error"]["code"] == "ALREADY_EXISTS"
        response, shader = await invoke(client, "create_script", uri="res://bad.gdshader", source="shader_type canvas_item;\nvoid fragment() { COLOR = unknown_symbol; }\n")
        assert response.is_error and shader["diagnostics"]["valid"] is False, shader
        response, diagnostics = await invoke(client, "get_diagnostics", uris=["res://bad.gdshader"])
        assert not response.is_error and diagnostics["sources"][0]["valid"] is False
        assert diagnostics["entries_are_history"] is True


async def test_batch_dependencies_drafts_and_preflight(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        changes = [
            {"uri": "res://dependent.gd", "create": True, "source": 'extends Node\nconst Later = preload("res://later.gd")\nfunc value() -> int:\n\treturn Later.answer()\n'},
            {"uri": "res://later.gd", "create": True, "source": "extends RefCounted\nstatic func answer() -> int:\n\treturn 42\n"},
        ]
        response, batch = await invoke(client, "apply_script_changes", changes=changes)
        assert not response.is_error, batch
        assert all(source["valid"] is True for source in batch["validation"]["sources"]), batch
        assert {doc["state"] for doc in batch["documents"]} == {"draft"}
        assert {doc["live_reload"] for doc in batch["documents"]} == {"deferred"}
        assert not (bridge.project / "dependent.gd").exists() and not (bridge.project / "later.gd").exists()
        assert batch["undo"]["scope"] == ["live_sources"]
        response, undone = await invoke(client, "undo_edit", edit_id=batch["edit_id"])
        assert not response.is_error, undone
        response, gone = await invoke(client, "read_script", uri="res://later.gd")
        assert response.is_error and gone["error"]["code"] == "FILE_NOT_FOUND", gone
        response, batch = await invoke(client, "apply_script_changes", changes=changes, save=True)
        assert all(source["valid"] is True for source in batch["validation"]["sources"]), batch
        assert batch["saved"] and batch["persistence"]["complete"]
        assert all((bridge.project / name).exists() for name in ["dependent.gd", "later.gd"])
        _, current = await invoke(client, "read_script", uri="res://later.gd")
        response, invalid_edit = await invoke(client, "apply_script_changes", changes=[
            {"uri": "res://must_not_exist.gd", "create": True, "source": "extends Node\n"},
            {"uri": "res://later.gd", "if_revision": "stale", "source": "extends Node\n"},
        ])
        assert response.is_error and invalid_edit["error"]["code"] == "REVISION_CONFLICT"
        response, absent = await invoke(client, "read_script", uri="res://must_not_exist.gd")
        assert response.is_error and absent["error"]["code"] == "FILE_NOT_FOUND"
        # A dependency-only unsaved API change invalidates a formerly valid dependent.
        await invoke(client, "edit_script", uri="res://later.gd", if_revision=current["revision"], source="extends RefCounted\nstatic func renamed() -> int:\n\treturn 42\n")
        response, fresh = await invoke(client, "get_diagnostics", uris=["res://dependent.gd"])
        assert not response.is_error and fresh["sources"][0]["valid"] is False, fresh
        assert "answer" in str(fresh["sources"][0]["entries"])
        assert "answer" in (bridge.project / "later.gd").read_text()
        _, current = await invoke(client, "read_script", uri="res://later.gd")
        await invoke(client, "edit_script", uri="res://later.gd", if_revision=current["revision"], source=changes[1]["source"])
        _, fresh = await invoke(client, "get_diagnostics", uris=["res://dependent.gd"])
        assert fresh["sources"][0]["valid"] is True, fresh

async def test_property_planner_rejects_incompatible_script_and_retries_attachment(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        await invoke(client, "create_nodes", parent=node(), nodes=[{"name": "Target", "class": "Node"}])
        response, created = await invoke(
            client,
            "create_script",
            uri="res://repairable.gd",
            source="extends Node2D\n",
            attach_to=[node("Target")],
        )
        assert response.is_error and created["status"] == "partial"
        retry = created["attachment_errors"][0]["retry"]
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
            uri="res://repairable.gd",
            if_revision=current["revision"],
            source="extends Node\n",
        )
        assert not response.is_error and repaired["diagnostics"]["valid"] is True
        await invoke(client, "get_diagnostics", uris=["res://repairable.gd"])
        await invoke(client, "save_documents", uris=["res://repairable.gd"])
        response, attached = await invoke(client, "update_nodes", **retry["arguments"])
        assert not response.is_error, attached
        _, after = await invoke(client, "get_resource", target={"node": node("Target"), "property": "script"}, properties=["source_code"])
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
        assert response.is_error and created["saved"] is True
        assert (bridge.project / "repairable.gdshader").exists()
        retry = created["attachment_errors"][0]["retry"]
        assert retry["tool"] == "update_resource"
        assert retry["arguments"]["scope"] == "shared"
        assert retry["arguments"]["target"] == {"uri": material_uri}
        Draft202012Validator(SPECS["update_resource"]["inputSchema"]).validate(retry["arguments"])

        _, current = await invoke(client, "read_script", uri="res://repairable.gdshader")
        response, repaired = await invoke(
            client,
            "edit_script",
            uri="res://repairable.gdshader",
            if_revision=current["revision"],
            source="shader_type canvas_item;\nvoid fragment() { COLOR = vec4(1.0); }\n",
        )
        assert not response.is_error and repaired["diagnostics"]["valid"] is True
        response, attached = await invoke(client, retry["tool"], **retry["arguments"])
        assert not response.is_error, attached
        _, material_after = await invoke(client, "get_resource", target={"uri": material_uri}, properties=["shader"])
        assert material_after["properties"]["shader"]["uri"] == "res://repairable.gdshader"
