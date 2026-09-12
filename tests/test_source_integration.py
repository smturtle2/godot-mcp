"""Source identity, save scope, dependency invalidation and guarded continuation."""
from __future__ import annotations

import os

import pytest
from mcp import Client
from test_source_workflow_integration import added, finished, invoke

from godot_mcp.server import create_server

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real editor")]


def node(path="."):
    return {"scene": "res://main.tscn", "path": path}


async def read(client, uri):
    response, value = await invoke(client, "read_scripts", documents=[{"uri": uri}])
    assert not response.is_error, value
    return value["documents"][0]


async def patch(client, text, **options):
    response, value = await invoke(client, "apply_script_changes", patch=text, wait_ms=0, **options)
    assert not response.is_error, value
    return await finished(client, value)


async def change(client, uri, old, new, **options):
    current = await read(client, uri)
    text = "\n".join(["*** Begin Patch", f"*** Update File: {uri}", "@@", *["-" + line for line in old.splitlines()], *["+" + line for line in new.splitlines()], "*** End Patch"])
    return await patch(client, text, base_revisions={uri: current["revision"]}, **options)


async def test_source_identity_explicit_save_scope_and_save_undo(editor):
    bridge, _ = editor
    uri = "res://identity.gd"
    async with Client(create_server(bridge.project, bridge)) as client:
        await invoke(client, "create_nodes", parent=node(), nodes=[{"name": "Good", "source": {"class": "Node2D"}}])
        created = await patch(client, added({uri: "extends Node2D\nvar answer: int = 1\n"}), save=True, attachments=[{"script": {"uri": uri, "node": node("Good")}}])
        assert created["status"] == "completed", created
        assert created["documents"][0]["state"] == "saved"
        await invoke(client, "set_breakpoints", breakpoints=[{"uri": uri, "line": 2}])
        assert (await read(client, uri))["buffer"] == "editor"
        changed = await change(client, uri, "var answer: int = 1", "var answer: int = 2")
        assert changed["status"] == "completed" and changed["documents"][0]["state"] == "modified", changed
        _, attached = await invoke(client, "get_resource", target={"node": {**node("Good"), "property": "script"}}, properties=["source_code"])
        assert attached["uri"] == uri and "= 2" in attached["properties"]["source_code"]
        assert "= 1" in (bridge.project / "identity.gd").read_text()
        before_scene = (bridge.project / "main.tscn").read_bytes()
        response, blocked = await invoke(client, "save_documents", uris=["res://main.tscn"])
        assert response.is_error and blocked["error"]["code"] == "SAVE_SCOPE_REQUIRED"
        assert (bridge.project / "main.tscn").read_bytes() == before_scene
        response, saved = await invoke(client, "save_documents", uris=[uri, "res://main.tscn", "res://missing.gd"])
        assert response.is_error and saved["status"] == "partial", saved
        saved = await finished(client, saved)
        assert {item["uri"]: item["save"]["state"] for item in saved["documents"]} == {
            uri: "saved",
            "res://main.tscn": "skipped",
            "res://missing.gd": "failed",
        }, saved
        assert 'path="res://identity.gd"' in (bridge.project / "main.tscn").read_text()
        response, undone = await invoke(client, "undo_edit", edit_id=changed["undo"]["edit_id"])
        assert not response.is_error, undone
        assert "= 1" in (await read(client, uri))["source"] and (await read(client, uri))["unsaved"]
        assert "= 2" in (bridge.project / "identity.gd").read_text()


async def test_partial_bindings_resume_only_remaining_after_source_repair(editor):
    bridge, _ = editor
    uri = "res://repairable.gd"
    async with Client(create_server(bridge.project, bridge)) as client:
        await invoke(client, "create_nodes", parent=node(), nodes=[{"name": "Good", "source": {"class": "Node2D"}}, {"name": "Bad", "source": {"class": "Node"}}])
        created = await patch(client, added({uri: "extends Node2D\n"}), save=True, attachments=[{"script": {"uri": uri, "node": node(name)}} for name in ["Good", "Bad"]])
        assert created["status"] == "partial" and created["resumable"] and created["phase"] == "bindings", created
        assert len(created["attachments"]) == 1 and len(created["undo"]["steps"]) == 2
        assert created["failures"][0]["recovery"]["tool"] == "resume_script_changes"
        repaired = await change(client, uri, "extends Node2D", "extends Node")
        assert repaired["status"] == "completed", repaired
        response, conflict = await invoke(client, "resume_script_changes", operation_id=created["operation_id"])
        assert response.is_error and conflict["error"]["code"] == "SOURCE_CHANGED", conflict
        current = await read(client, uri)
        response, resumed = await invoke(client, "resume_script_changes", operation_id=created["operation_id"], revisions={uri: current["revision"]}, wait_ms=0)
        assert not response.is_error, resumed
        resumed = await finished(client, resumed)
        assert resumed["status"] == "completed" and not resumed["resumable"], resumed
        assert len(resumed["attachments"]) == 2 and len(resumed["undo"]["steps"]) == 3, resumed
        assert len(resumed["attempts"]) == 1
        for name in ["Good", "Bad"]:
            _, attached = await invoke(client, "get_resource", target={"node": {**node(name), "property": "script"}})
            assert attached["uri"] == uri
        assert "extends Node\n" == (bridge.project / "repairable.gd").read_text()


async def test_dependency_only_unsaved_changes_invalidate_current_diagnostics(editor):
    bridge, _ = editor
    source = "extends RefCounted\nstatic func answer() -> int:\n\treturn 42\n"
    async with Client(create_server(bridge.project, bridge)) as client:
        created = await patch(client, added({"res://dependent.gd": 'extends Node\nconst Later = preload("res://later.gd")\nfunc value() -> int:\n\treturn Later.answer()\n', "res://later.gd": source}), save=True)
        assert created["status"] == "completed", created
        changed = await change(client, "res://later.gd", "static func answer() -> int:", "static func renamed() -> int:")
        assert changed["status"] == "completed", changed
        _, request = await invoke(client, "get_diagnostics", uris=["res://dependent.gd"], wait_ms=0)
        invalid = await finished(client, request)
        assert invalid["state"] == "invalid" and invalid["sources"][0]["valid"] is False, invalid
        assert "answer" in str(invalid["sources"][0]["entries"])
        assert "answer" in (bridge.project / "later.gd").read_text()
        await change(client, "res://later.gd", "static func renamed() -> int:", "static func answer() -> int:")
        _, request = await invoke(client, "get_diagnostics", uris=["res://dependent.gd"], wait_ms=0)
        valid = await finished(client, request)
        assert valid["state"] == "valid" and valid["error_count"] == 0, valid


async def test_invalid_shader_repair_then_resume_and_draft_attachment_save(editor):
    bridge, _ = editor
    uri = "res://repairable.gdshader"
    async with Client(create_server(bridge.project, bridge)) as client:
        _, material = await invoke(client, "create_resource", **{"class": "ShaderMaterial"}, save_as="res://material.tres")
        material_uri = material["resource"]["uri"]
        created = await patch(client, added({uri: "shader_type canvas_item;\nvoid fragment() { COLOR = unknown_symbol; }\n"}), attachments=[{"shader": {"uri": uri, "target": {"shared": {"uri": material_uri}}}}])
        assert created["status"] == "partial" and created["phase"] == "bindings", created
        assert created["failures"][0]["code"] == "SOURCE_NOT_SAVED", created
        assert created["documents"][0]["state"] == "draft" and not (bridge.project / "repairable.gdshader").exists()
        _, diagnostics = await invoke(client, "get_diagnostics", uris=[uri], wait_ms=0)
        diagnostics = await finished(client, diagnostics)
        assert diagnostics["state"] == "invalid" and diagnostics["sources"][0]["valid"] is False, diagnostics
        repaired = await change(client, uri, "void fragment() { COLOR = unknown_symbol; }", "void fragment() { COLOR = vec4(1.0); }")
        assert repaired["status"] == "completed", repaired
        current = await read(client, uri)
        _, resumed = await invoke(client, "resume_script_changes", operation_id=created["operation_id"], revisions={uri: current["revision"]}, wait_ms=0)
        blocked = await finished(client, resumed)
        assert blocked["status"] == "partial" and blocked["failures"][0]["code"] == "SOURCE_NOT_SAVED", blocked
        await invoke(client, "save_documents", uris=[uri])
        _, resumed = await invoke(client, "resume_script_changes", operation_id=created["operation_id"], wait_ms=0)
        attached = await finished(client, resumed)
        assert attached["status"] == "completed", attached
        assert attached["documents"][0]["live_reload"] == "succeeded"
        _, current_material = await invoke(client, "get_resource", target={"uri": material_uri}, properties=["shader"])
        assert current_material["properties"]["shader"]["uri"] == uri


async def test_document_detail_save_as_attempts(editor):
    bridge, _ = editor
    uri, moved_uri = "res://format_modes.gd", "res://format_modes_moved.gd"
    async with Client(create_server(bridge.project, bridge)) as client:
        created = await patch(client, added({uri: "extends Node\nvar number: int = 1\n"}), save=True)
        document = created["documents"][0]
        assert {"disk_revision", "base_disk_revision", "baseline_known"} <= document.keys()
        assert "validation" not in document
        response, saved = await invoke(client, "save_documents", uris=[uri], save_as={uri: moved_uri})
        assert not response.is_error, saved
        moved = (await finished(client, saved))["documents"]
        assert len(moved) == 1 and moved[0]["uri"] == moved_uri and moved[0]["save"]["previous_uri"] == uri
        await change(client, moved_uri, "var number: int = 1", "var number: int = 2")
        response, repeated = await invoke(client, "save_documents", uris=[moved_uri, moved_uri])
        assert not response.is_error, repeated
        records = (await finished(client, repeated))["documents"]
        assert len(records) == 1 and [item["index"] for item in records[0]["save"]["attempts"]] == [0, 1]
