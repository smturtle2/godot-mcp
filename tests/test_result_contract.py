import asyncio
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from godot_mcp.bridge import ToolError
from godot_mcp.catalog import SPECS, TOOL_SPECS
from godot_mcp.server import create_server


class FakeBridge:
    def __init__(self, project: Path, responses: dict):
        self.project = project.resolve()
        self.responses = responses
        self.calls = []

    async def call(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        response = self.responses.get(name)
        if isinstance(response, Exception):
            raise response
        return response


def run_call(project: Path, responses: dict, name: str, arguments: dict, *, bridge=None):
    async def exercise():
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            server = create_server(project, bridge or FakeBridge(project, responses))
            task = asyncio.create_task(server.run(*server_streams, server.create_initialization_options()))
            try:
                async with ClientSession(*client_streams) as client:
                    await client.initialize()
                    return await client.call_tool(name, arguments)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    result = asyncio.run(exercise())
    assert json.loads(result.content[0].text) == result.structured_content
    return result


def validation_source(uri: str, state: str = "valid", valid=True) -> dict:
    return {"uri": uri, "revision": "rev", "state": state, "valid": valid, "scope": "snapshot", "entries": []}


def document(uri: str, state: str = "modified") -> dict:
    return {"uri": uri, "effect": "updated", "state": state, "revision": "rev", "disk_revision": "disk",
            "base_disk_revision": "disk", "baseline_known": True, "conflict": "none",
            "validation": {"state": "valid", "scope": "snapshot", "entries": []}}


def document_result(record: dict, *, status="completed", failures=None):
    return {"operation_id": "operation-test-1", "details_retained": True, "status": status, "complete": status == "completed", "documents": [record],
            "failures": failures or [], "pending": [], "undo": {"edit_id": None, "scope": [], "retained_files": []},
            "pending_save": []}


def test_tools_list_publishes_current_inputs_and_matching_output_contracts(tmp_path):
    async def exercise():
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            server = create_server(tmp_path, FakeBridge(tmp_path, {}))
            task = asyncio.create_task(server.run(*server_streams, server.create_initialization_options()))
            try:
                async with ClientSession(*client_streams) as client:
                    await client.initialize()
                    return {tool.name: tool for tool in (await client.list_tools()).tools}
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    tools = asyncio.run(exercise())
    assert set(tools) == set(SPECS)
    for spec in TOOL_SPECS:
        name = spec["name"]
        Draft202012Validator.check_schema(spec["inputSchema"])
        assert tools[name].input_schema == spec["inputSchema"]
        if "outputSchema" in spec:
            schema = spec["outputSchema"]
            Draft202012Validator.check_schema(schema)
            assert tools[name].model_dump(by_alias=True)["outputSchema"] == schema
    assert "oneOf" not in tools["send_input"].input_schema["properties"]["events"]["items"]
    assert "event" in SPECS["send_input"]["inputSchema"]["properties"]["events"]["items"]["required"]


@pytest.mark.parametrize("name,arguments,path", [
    ("send_input", {"run_id": "run-1", "events": [{"event": {"key": {"pressed": True}}}]}, ["events", 0, "event", "key", "key"]),
    ("get_resource", {"target": {"uri": "res://a.tres", "node": {"scene": "res://main.tscn", "path": ".", "property": "material"}}}, ["target"]),
    ("edit_tileset", {"target": {"local": {"scene": "res://main.tscn", "path": "."}}, "changes": [{"add_physics_layer": {}}]}, ["target", "local", "property"]),
])
def test_strict_conditional_rules_reject_before_bridge_call(tmp_path, name, arguments, path):
    bridge = FakeBridge(tmp_path, {})
    result = run_call(tmp_path, {}, name, arguments, bridge=bridge)
    assert result.is_error and result.structured_content["error"]["code"] == "INVALID_ARGUMENT"
    assert result.structured_content["error"]["details"]["path"] == path
    assert bridge.calls == []


def test_mutation_receipt_and_detail_query_preserve_bridge_payload_without_reexecution(tmp_path):
    payload = document_result(document("res://a.gd", "saved"))
    payload["documents"][0].update(effect="created", save={"state": "saved"}, live_reload="succeeded")
    original = copy.deepcopy(payload)
    snapshot = {"operation_id": payload["operation_id"], "tool": "create_script", "editor_epoch": "test", "recorded_at_usec": 5,
                "snapshot": True, "pending": False, "result": payload, "current_undo": {"edit_id": None, "available": False}}
    bridge = FakeBridge(tmp_path, {"create_script": payload, "get_operation_result": snapshot})
    result = run_call(tmp_path, {}, "create_script", {"uri": "res://a.gd", "source": "extends Node\n"}, bridge=bridge)
    assert not result.is_error and payload == original
    record = result.structured_content["documents"][0]
    assert "disk_revision" not in record and "entries" not in record["validation"]
    details = run_call(tmp_path, {}, "get_operation_result", {"operation_id": payload["operation_id"]}, bridge=bridge)
    assert not details.is_error and details.structured_content["result"] == original
    assert bridge.calls == [("create_script", {"uri": "res://a.gd", "source": "extends Node\n"}), ("get_operation_result", {"operation_id": payload["operation_id"]})]
    Draft202012Validator(SPECS["create_script"]["outputSchema"]).validate(result.structured_content)
    Draft202012Validator(SPECS["get_operation_result"]["outputSchema"]).validate(details.structured_content)


def test_partial_create_preserves_applied_file_diagnostics_and_recovery(tmp_path):
    record = document("res://broken.gd", "saved")
    record.update(effect="created", save={"state": "saved"}, live_reload="not_attempted")
    record["validation"] = {"state": "invalid", "scope": "snapshot", "entries": [{"kind": "error", "message": "Syntax error", "line": 2}]}
    failure = {"phase": "validation", "code": "SOURCE_INVALID", "message": "Repair source.", "uri": record["uri"],
               "recovery": {"tool": "get_diagnostics", "arguments": {"uris": [record["uri"]]}}}
    payload = document_result(record, status="partial", failures=[failure])
    payload["undo"]["retained_files"] = [record["uri"]]
    result = run_call(tmp_path, {"create_script": payload}, "create_script", {"uri": record["uri"], "source": "extends Node\n"})
    assert result.is_error
    data = result.structured_content
    assert data["status"] == "partial" and "complete" not in data
    assert data["documents"][0]["state"] == "saved" and data["documents"][0]["validation"]["state"] == "invalid"
    assert data["failures"] == [failure] and data["undo"]["retained_files"] == [record["uri"]]
    Draft202012Validator(SPECS["create_script"]["outputSchema"]).validate(data)


def test_invalid_diagnostics_are_a_successful_result(tmp_path):
    payload = {"entries": [], "sources": [validation_source("res://broken.gd", "invalid", False)],
               "entries_are_history": True, "origin": "editor"}
    result = run_call(tmp_path, {"get_diagnostics": payload}, "get_diagnostics", {"uris": ["res://broken.gd"]})
    assert not result.is_error
    assert result.structured_content["sources"][0]["state"] == "invalid"


@pytest.mark.parametrize("status", ["completed", "partial", "failed"])
def test_document_operation_status_maps_to_mcp_is_error(tmp_path, status):
    record = {"uri": "res://main.tscn", "save": {"state": "saved" if status == "completed" else "failed"}}
    payload = document_result(record, status=status)
    result = run_call(tmp_path, {"save_documents": payload}, "save_documents", {"uris": [record["uri"]]})
    assert result.is_error == (status != "completed")
    assert result.structured_content["status"] == status


def test_tool_error_remains_an_error_response(tmp_path):
    result = run_call(tmp_path, {"read_script": ToolError("FILE_NOT_FOUND", "missing")}, "read_script", {"uri": "res://missing.gd"})
    assert result.is_error
    assert result.structured_content["error"]["code"] == "FILE_NOT_FOUND"


def test_partial_send_input_preserves_effects_and_nested_failures(tmp_path):
    payload = {"status": "partial", "complete": False, "failures": [{"phase": "capture", "code": "CAPTURE_FAILED", "message": "capture unavailable", "details": {"display": "headless"}}], "pending": [], "processed": 2, "elapsed_ms": 30, "held_inputs": 1, "capture": {"error": {"code": "CAPTURE_FAILED", "message": "capture unavailable"}}, "recovery": "Retry capture.", "run_id": "run-1", "observed_at_usec": 2_147_483_648, "frame": 2_147_483_648}
    result = run_call(tmp_path, {"send_input": payload}, "send_input", {"run_id": "run-1", "events": [{"event": {"key": {"key": "Space", "pressed": True}}}]})
    assert result.is_error
    assert result.structured_content["processed"] == 2
    assert result.structured_content["failures"][0]["details"]["display"] == "headless"
    Draft202012Validator(SPECS["send_input"]["outputSchema"]).validate(result.structured_content)


def test_nested_images_are_extracted_from_a_copy_and_json_matches_structure(tmp_path):
    payload = {"status": "completed", "complete": True, "failures": [], "pending": [], "processed": 1,
               "elapsed_ms": 0, "held_inputs": 0, "capture": {"image_base64": "aGVsbG8=", "width": 1, "height": 1}}
    original = copy.deepcopy(payload)
    result = run_call(tmp_path, {"send_input": payload}, "send_input", {"run_id": "run-1", "events": [{"event": {"action": {"action": "ui_accept", "pressed": True}}}]})
    assert not result.is_error and payload == original
    assert result.structured_content["capture"] == {"width": 1, "height": 1}
    assert result.content[1].type == "image" and result.content[1].data == "aGVsbG8="


def test_completed_import_assets_preserves_operation_and_undo_contract(tmp_path):
    payload = {"status": "completed", "complete": True, "failures": [], "pending": [], "operation_id": "op-1", "phase": "completed", "saved": True, "files_written": ["res://a.png"], "options_changed": [], "changed_paths": ["res://a.png.import"], "assets": [{"uri": "res://a.png", "imported": True, "resource": {"$type": "Resource", "uri": "res://a.png", "class": "CompressedTexture2D"}, "preservation": "kept"}], "edit_id": "edit-1", "undo_state": "available", "undo": {"edit_id": "edit-1", "scope": ["files"]}}
    result = run_call(tmp_path, {"import_assets": payload}, "import_assets", {"files": [{"destination": "res://a.png"}]})
    assert not result.is_error
    assert result.structured_content["operation_id"] == "op-1"
    Draft202012Validator(SPECS["import_assets"]["outputSchema"]).validate(result.structured_content)
