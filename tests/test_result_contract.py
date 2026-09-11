import asyncio
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from godot_mcp.bridge import ToolError
from godot_mcp.catalog import SPECS
from godot_mcp.server import create_server


class FakeBridge:
    def __init__(self, project: Path, responses: dict):
        self.project = project.resolve()
        self.responses = responses

    async def call(self, name: str, _arguments: dict) -> dict:
        response = self.responses.get(name)
        if isinstance(response, Exception):
            raise response
        return response


def run_call(project: Path, responses: dict, name: str, arguments: dict):
    async def exercise():
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            server = create_server(project, FakeBridge(project, responses))
            task = asyncio.create_task(server.run(*server_streams, server.create_initialization_options()))
            try:
                async with ClientSession(*client_streams) as client:
                    await client.initialize()
                    return await client.call_tool(name, arguments)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    return asyncio.run(exercise())


def validation_source(uri: str, state: str = "valid", valid=True) -> dict:
    return {"uri": uri, "revision": "rev", "state": state, "valid": valid, "scope": "snapshot", "entries": []}


def document(uri: str, state: str = "modified") -> dict:
    return {"uri": uri, "state": state, "revision": "rev", "disk_revision": "disk", "saved": state == "saved"}


def test_source_tools_publish_structurally_valid_output_schemas_and_tools_list(tmp_path):
    names = ["create_script", "edit_script", "apply_script_changes", "save_documents", "read_script", "get_diagnostics", "send_input", "import_assets"]

    async def exercise():
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            server = create_server(tmp_path, FakeBridge(tmp_path, {}))
            task = asyncio.create_task(server.run(*server_streams, server.create_initialization_options()))
            try:
                async with ClientSession(*client_streams) as client:
                    await client.initialize()
                    tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                    return tools
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    tools = asyncio.run(exercise())
    for name, spec in SPECS.items():
        assert tools[name].input_schema == spec["inputSchema"]
    for name in names:
        assert name in tools
        schema = SPECS[name]["outputSchema"]
        Draft202012Validator.check_schema(schema)
        assert tools[name].model_dump(by_alias=True)["outputSchema"] == schema
    assert "create_nodes" in tools and "send_input" in tools
    assert tools["create_nodes"].input_schema["type"] == "object"
    assert tools["send_input"].input_schema["type"] == "object"
    assert "oneOf" in tools["send_input"].input_schema["properties"]["events"]["items"]


def test_partial_create_preserves_file_state_and_diagnostics_but_is_error(tmp_path):
    payload = {"uri": "res://broken.gd", "revision": "rev", "saved": True,
               "diagnostics": validation_source("res://broken.gd", "invalid", False),
               "attached": [], "attachment_errors": [], "status": "partial",
               "summary": "Source file remains saved.", "document": document("res://broken.gd", "saved"),
               "undo": {"scope": [], "retained_files": ["res://broken.gd"]}, "pending_save": []}
    result = run_call(tmp_path, {"create_script": payload}, "create_script", {"uri": "res://broken.gd", "source": "extends Node\n"})
    assert result.is_error
    assert result.structured_content["status"] == "partial"
    assert result.structured_content["document"]["state"] == "saved"
    assert result.structured_content["diagnostics"]["valid"] is False
    Draft202012Validator(SPECS["create_script"]["outputSchema"]).validate(result.structured_content)


def test_invalid_diagnostics_are_a_successful_result(tmp_path):
    payload = {"entries": [], "sources": [validation_source("res://broken.gd", "invalid", False)],
               "entries_are_history": True, "origin": "editor"}
    result = run_call(tmp_path, {"get_diagnostics": payload}, "get_diagnostics", {"uris": ["res://broken.gd"]})
    assert not result.is_error
    assert result.structured_content["sources"][0]["state"] == "invalid"


def test_partial_save_and_completed_result_map_to_error_status(tmp_path):
    partial = {"saved": [], "failed": [{"uri": "res://a.gd", "error": "write failed"}], "complete": False,
               "status": "partial", "summary": "Some documents were not saved.", "undo": {"scope": []}}
    completed = {"saved": [{"uri": "res://a.gd", "saved_as": "res://a.gd"}], "failed": [], "complete": True,
                 "status": "completed", "summary": "Specified documents saved.", "undo": {"scope": []}}
    partial_result = run_call(tmp_path, {"save_documents": partial}, "save_documents", {"uris": ["res://a.gd"]})
    complete_result = run_call(tmp_path, {"save_documents": completed}, "save_documents", {"uris": ["res://a.gd"]})
    assert partial_result.is_error and partial_result.structured_content["failed"]
    assert not complete_result.is_error and complete_result.structured_content["complete"]


def test_tool_error_remains_an_error_response(tmp_path):
    result = run_call(tmp_path, {"read_script": ToolError("FILE_NOT_FOUND", "missing")}, "read_script", {"uri": "res://missing.gd"})
    assert result.is_error
    assert result.structured_content["error"]["code"] == "FILE_NOT_FOUND"


def test_partial_send_input_preserves_effects_and_nested_failures(tmp_path):
    payload = {"status": "partial", "complete": False, "failures": [{"phase": "capture", "code": "CAPTURE_FAILED", "message": "capture unavailable", "details": {"display": "headless"}}], "pending": [], "processed": 2, "elapsed_ms": 30, "held_inputs": 1, "capture": {"error": {"code": "CAPTURE_FAILED", "message": "capture unavailable"}}, "recovery": "Retry capture.", "run_id": "run-1", "observed_at_usec": 2_147_483_648, "frame": 2_147_483_648}
    result = run_call(tmp_path, {"send_input": payload}, "send_input", {"run_id": "run-1", "events": [{"type": "key", "key": "Space", "pressed": True}]})
    assert result.is_error
    assert result.structured_content["processed"] == 2
    assert result.structured_content["failures"][0]["details"]["display"] == "headless"
    Draft202012Validator(SPECS["send_input"]["outputSchema"]).validate(result.structured_content)


def test_completed_import_assets_preserves_operation_and_undo_contract(tmp_path):
    payload = {"status": "completed", "complete": True, "failures": [], "pending": [], "operation_id": "op-1", "phase": "completed", "saved": True, "files_written": ["res://a.png"], "options_changed": [], "changed_paths": ["res://a.png.import"], "assets": [{"uri": "res://a.png", "imported": True, "resource": {"$type": "Resource", "uri": "res://a.png", "class": "CompressedTexture2D"}, "preservation": "kept"}], "edit_id": "edit-1", "undo_state": "available", "undo": {"edit_id": "edit-1", "scope": ["files"]}}
    result = run_call(tmp_path, {"import_assets": payload}, "import_assets", {"files": [{"destination": "res://a.png"}]})
    assert not result.is_error
    assert result.structured_content["operation_id"] == "op-1"
    Draft202012Validator(SPECS["import_assets"]["outputSchema"]).validate(result.structured_content)
