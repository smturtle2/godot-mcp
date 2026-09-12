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
                {"key": "child", "parent_key": "parent", "name": "Child", "source": {"class": "Node2D"}},
                {"key": "parent", "name": "Parent", "source": {"class": "Node2D"}},
                {"key": "grandchild", "parent_key": "child", "name": "Grandchild", "source": {"class": "Node2D"}},
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

        ui = await client.call_tool("create_nodes", {
            "parent": {"scene": "res://main.tscn", "path": "."},
            "nodes": [
                {"key": "panel", "name": "Panel", "source": {"class": "Control"}, "layout": {"preset": "full_rect"}},
                {"name": "Button", "parent_key": "panel", "source": {"class": "Button"},
                 "properties": {"layout_mode": 1, "text": "Play"}, "layout": {"preset": "center", "minimum_size": {"x": 120, "y": 40}}},
                {"name": "Mesh", "source": {"class": "MeshInstance3D"}, "properties": {
                    "mesh": {"$type": "Resource", "class": "BoxMesh", "properties": {
                        "material": {"$type": "Resource", "class": "StandardMaterial3D", "properties": {"roughness": 0.7}}}}}},
            ],
        })
        assert not ui.is_error, ui
        button = {"scene": "res://main.tscn", "path": "Panel/Button"}
        changed = await client.call_tool("update_nodes", {"changes": [{"node": button, "set": {"text": "Go"}}]})
        receipt = changed.structured_content["nodes"][0]
        assert receipt == {"ref": button, "properties": {"text": "Go"}}
        assert "affected_references" not in changed.structured_content
        saved = await client.call_tool("create_resource", {"class": "StandardMaterial3D", "save_as": "res://saved.tres"})
        assert not saved.is_error and saved.structured_content["resource"]["uri"] == "res://saved.tres"
        inspected = await client.call_tool("get_resource", {"target": {"uri": "res://saved.tres"}, "properties": ["roughness"]})
        assert not inspected.is_error
        invalid = await client.call_tool("create_nodes", {
            "parent": {"scene": "res://main.tscn", "path": "."},
            "nodes": [{"name": "Valid", "source": {"class": "Node"}}, {"name": "Bad/Name", "source": {"class": "Node"}}],
        })
        assert error_code(invalid) == "INVALID_NAME"
        assert invalid.structured_content["error"]["details"]["index"] == 1
        assert invalid.structured_content["error"]["details"]["name"] == "Bad/Name"
        invalid_property = await client.call_tool("create_nodes", {
            "parent": {"scene": "res://main.tscn", "path": "."},
            "nodes": [{"name": "Broken", "source": {"class": "Control"}, "properties": {"nonexistent": 42}}],
        })
        assert invalid_property.structured_content["error"]["details"]["field"] == "nodes[0].properties.nonexistent"

        for nodes, code, name in [
            ([{"name": "MissingParent", "parent_key": "absent", "source": {"class": "Node2D"}}], "UNKNOWN_PARENT_KEY", "MissingParent"),
            ([{"key": "same", "name": "DuplicateA", "source": {"class": "Node2D"}},
              {"key": "same", "name": "DuplicateB", "source": {"class": "Node2D"}}], "DUPLICATE_KEY", "DuplicateA"),
            ([{"key": "cycle_a", "parent_key": "cycle_b", "name": "CycleA", "source": {"class": "Node2D"}},
              {"key": "cycle_b", "parent_key": "cycle_a", "name": "CycleB", "source": {"class": "Node2D"}}], "PARENT_CYCLE", "CycleA"),
        ]:
            rejected = await client.call_tool("create_nodes", {
                "parent": {"scene": "res://main.tscn", "path": "."}, "nodes": nodes,
            })
            assert error_code(rejected) == code
            after = await client.call_tool("get_scene", {"depth": 1})
            assert name not in {child["name"] for child in after.structured_content["root"]["children"]}
