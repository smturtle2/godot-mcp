"""Real-editor regression coverage for flat scene creation and scene projections."""
from __future__ import annotations

import os

import pytest
from mcp import Client

from godot_mcp.server import create_server

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real editor"
)]


def error_code(result):
    assert result.is_error, result
    return result.structured_content["error"]["code"]


async def test_flat_create_and_get_scene_contract(editor):
    bridge, _ = editor
    server = create_server(bridge.project, bridge)
    async with Client(server) as client:
        created = await client.call_tool("create_nodes", {
            "parent": {"scene": "res://main.tscn", "path": "."},
            "nodes": [
                {"key": "child", "parent_key": "parent", "name": "Child", "class": "Node2D"},
                {"key": "parent", "name": "Parent", "class": "Node2D"},
                {"key": "grandchild", "parent_key": "child", "name": "Grandchild", "class": "Node2D"},
            ],
        })
        assert not created.is_error
        returned = {item["key"]: item["ref"] for item in created.structured_content["nodes"]}
        assert returned["parent"]["path"] == "Parent"
        assert returned["child"]["path"] == "Parent/Child"
        assert returned["grandchild"]["path"] == "Parent/Child/Grandchild"

        default = await client.call_tool("get_scene", {})
        assert not default.is_error
        root = default.structured_content["root"]
        assert all(field not in root for field in ("properties", "layout", "overrides", "connections"))

        queried = await client.call_tool("get_scene", {"properties": ["position"], "depth": 0})
        queried_root = queried.structured_content["root"]
        assert set(queried_root["properties"]) == {"position"}

        included_all = await client.call_tool("get_scene", {"include": ["properties"], "depth": 0})
        assert included_all.structured_content["root"].get("properties")

        included_none = await client.call_tool("get_scene", {"include": ["properties"], "properties": [], "depth": 0})
        assert included_none.structured_content["root"]["properties"] == {}

        shallow = await client.call_tool("get_scene", {"depth": 1})
        shallow_root = shallow.structured_content["root"]
        assert shallow_root["children"][0]["name"] == "Parent"
        assert shallow_root["children"][0]["children"] == []
        assert shallow.structured_content["truncated"]
        assert shallow.structured_content["depth_truncated"]

        for nodes, code, name in [
            ([{"name": "MissingParent", "parent_key": "absent", "class": "Node2D"}], "UNKNOWN_PARENT_KEY", "MissingParent"),
            ([{"key": "same", "name": "DuplicateA", "class": "Node2D"},
              {"key": "same", "name": "DuplicateB", "class": "Node2D"}], "DUPLICATE_KEY", "DuplicateA"),
            ([{"key": "cycle_a", "parent_key": "cycle_b", "name": "CycleA", "class": "Node2D"},
              {"key": "cycle_b", "parent_key": "cycle_a", "name": "CycleB", "class": "Node2D"}], "PARENT_CYCLE", "CycleA"),
        ]:
            rejected = await client.call_tool("create_nodes", {
                "parent": {"scene": "res://main.tscn", "path": "."}, "nodes": nodes,
            })
            assert error_code(rejected) == code
            after = await client.call_tool("get_scene", {"depth": 1})
            assert name not in {child["name"] for child in after.structured_content["root"]["children"]}
