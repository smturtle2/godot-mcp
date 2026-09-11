from jsonschema import Draft202012Validator

from godot_mcp.catalog import SPECS, TOOL_SPECS


def validator(name):
    return Draft202012Validator(SPECS[name]["inputSchema"])


def assert_valid(name, value):
    errors = list(validator(name).iter_errors(value))
    assert not errors, errors


def assert_invalid(name, value):
    assert list(validator(name).iter_errors(value)), f"unexpectedly accepted: {value!r}"


def test_catalog_has_exactly_44_unique_json_tool_schemas():
    names = [spec["name"] for spec in TOOL_SPECS]
    assert len(names) == 44
    assert len(set(names)) == 44
    assert set(names) == set(SPECS)
    for spec in TOOL_SPECS:
        schema = spec["inputSchema"]
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        Draft202012Validator.check_schema(schema)


def test_representative_nested_examples_validate():
    assert_valid("create_nodes", {
        "parent": {"scene": "res://main.tscn", "path": "root/Main"},
        "nodes": [{"key": "player", "name": "Player", "class": "CharacterBody2D", "properties": {
            "position": {"$type": "Vector2", "x": 10, "y": 20},
        }}, {"key": "sprite", "parent_key": "player", "name": "Sprite", "instance": "res://player.tscn"}],
    })
    assert_valid("update_resource", {
        "target": {"node": {"scene": "res://main.tscn", "path": "root/Main"}, "property": "material"},
        "set": {"albedo": {"$type": "Color", "r": 1, "g": 0.5, "b": 0, "a": 1}},
        "scope": "node",
    })
    assert_valid("edit_animation_graph", {
        "tree": {"scene": "res://main.tscn", "path": "root/Main/AnimationTree"},
        "root_type": "blend_tree",
        "states": [{"name": "walk", "animation": "walk", "position": {"x": 0, "y": 0}}],
        "nodes": [{"name": "speed", "kind": "blend_space_1d", "points": [
            {"animation": "idle", "position": {"$type": "Vector2", "x": 0, "y": 0}}
        ]}],
    })
    assert_valid("send_input", {"run_id": "run-1", "events": [
        {"type": "key", "key": "Space", "pressed": True},
        {"type": "mouse_button", "button": "left", "position": {"x": 12, "y": 8}, "pressed": False},
    ]})


def test_contract_rejects_unknown_args_traversal_invalid_revision_and_duration():
    assert_invalid("get_context", {"scope": "all", "unexpected": True})
    assert_invalid("edit_script", {"uri": "res://main.gd", "if_revision": "", "edits": []})
    assert_invalid("wait_for_condition", {"run_id": "r", "condition": {"type": "scene", "uri": "res://main.tscn"}, "timeout_ms": -1})
    assert_invalid("export_build", {"preset": "linux", "output": "file:///tmp/a", "timeout_ms": -1})


def test_scene_include_and_script_source_batch_contracts():
    assert_valid("get_scene", {"include": ["layout", "properties"], "properties": []})
    assert_valid("edit_script", {"uri": "res://main.gd", "if_revision": "r1", "source": "extends Node\n"})
    assert_valid("apply_script_changes", {"changes": [
        {"uri": "res://new.gd", "create": True, "source": "extends Node\n"},
        {"uri": "res://main.gd", "if_revision": "r1", "edits": [{
            "range": {"start": {"line": 1, "column": 1}, "end": {"line": 1, "column": 1}}, "text": "# batch\n",
        }]},
    ], "save": True})
    assert_invalid("edit_script", {"uri": "res://main.gd", "if_revision": "r1", "source": "x", "edits": []})
    assert_invalid("apply_script_changes", {"changes": [
        {"uri": "res://new.gd", "create": True, "if_revision": "r1", "source": "x"},
    ]})
    assert_invalid("apply_script_changes", {"changes": [
        {"uri": "res://main.gd", "source": "x"},
    ]})


def test_flat_create_nodes_and_strict_input_variants_have_no_refs():
    assert_valid("create_nodes", {"parent": {"scene": "res://main.tscn", "path": "root/Main"}, "nodes": [
        {"key": "player", "name": "Player", "class": "CharacterBody2D"},
        {"key": "sprite", "parent_key": "player", "name": "Sprite", "instance": "res://player.tscn"},
    ]})
    assert_invalid("create_nodes", {"parent": {"scene": "res://main.tscn", "path": "root/Main"}, "nodes": [
        {"name": "Player", "class": "CharacterBody2D", "children": []},
    ]})
    assert_invalid("send_input", {"run_id": "run-1", "events": [{"type": "key", "pressed": True}]})
    assert_invalid("send_input", {"run_id": "run-1", "events": [
        {"type": "key", "key": "Space", "pressed": True, "position": {"x": 1, "y": 2}},
    ]})

    def has_ref(value):
        if isinstance(value, dict):
            return "$ref" in value or any(has_ref(child) for child in value.values())
        return any(has_ref(child) for child in value) if isinstance(value, list) else False

    assert not has_ref(SPECS["create_nodes"]["inputSchema"])
    assert not has_ref(SPECS["send_input"]["inputSchema"])
