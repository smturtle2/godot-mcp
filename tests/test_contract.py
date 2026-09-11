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
    assert_valid("edit_script", {"project": "/tmp/project", "uri": "res://main.gd", "if_revision": "r1", "source": "extends Node\n"})
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


def test_union_item_shapes_are_named_and_keep_variant_requirements():
    nodes = SPECS["create_nodes"]["inputSchema"]["properties"]["nodes"]["items"]
    assert set(nodes["properties"]) >= {"key", "parent_key", "name", "class", "instance", "duplicate", "properties"}
    assert all(set(variant["properties"]) >= set(nodes["properties"]) for variant in nodes["oneOf"])
    assert_invalid("create_nodes", {"parent": {"scene": "res://main.tscn", "path": "root"},
                                     "nodes": [{"name": "Thing"}]})

    edit = SPECS["edit_script"]["inputSchema"]
    assert all(set(variant["properties"]) >= {"uri", "if_revision", "source", "edits"}
               for variant in edit["oneOf"])
    assert_valid("edit_script", {"uri": "res://main.gd", "if_revision": "r1", "edits": [
        {"range": {"start": {"line": 1, "column": 1}, "end": {"line": 1, "column": 1}}, "text": "# edit\n"},
    ]})
    assert_valid("edit_script", {"project": "/tmp/project", "uri": "res://main.gd", "if_revision": "r1", "edits": [
        {"range": {"start": {"line": 1, "column": 1}, "end": {"line": 1, "column": 1}}, "text": "# edit\n"},
    ]})


def test_resource_and_condition_union_shapes_are_explicit():
    resource = SPECS["get_resource"]["inputSchema"]["properties"]["target"]
    assert [set(variant["properties"]) for variant in resource["oneOf"]] == [{"uri"}, {"node", "property"}]
    assert_valid("get_resource", {"target": {"uri": "res://material.tres"}})
    assert_invalid("get_resource", {"target": {"node": {"scene": "res://main.tscn", "path": "root"}}})

    condition = SPECS["wait_for_condition"]["inputSchema"]["properties"]["condition"]
    assert len(condition["oneOf"]) == 4
    assert all(set(variant["properties"]) >= {"type", "uri", "node", "property", "value", "signal"}
               for variant in condition["oneOf"])
    assert_valid("wait_for_condition", {"run_id": "run-1", "condition": {
        "type": "property", "node": {"run_id": "run-1", "path": "/root/Main"},
        "property": "visible", "value": True,
    }})


def test_animation_track_shape_and_action_descriptions_are_preserved():
    tracks = SPECS["edit_animation"]["inputSchema"]["properties"]["tracks"]["items"]
    assert set(tracks["properties"]) >= {"op", "index", "kind", "path", "keys"}
    assert all(set(variant["properties"]) >= set(tracks["properties"]) for variant in tracks["anyOf"])
    assert "exactly one of class, instance, or duplicate" in SPECS["create_nodes"]["description"]
    assert "complete source replacement or one or more range edits" in SPECS["edit_script"]["description"]


def test_resource_node_scope_and_input_timestamp_bounds_are_enforced():
    node_target = {"node": {"scene": "res://main.tscn", "path": "root/Main"}, "property": "material"}
    assert_valid("update_resource", {"target": node_target, "set": {}, "scope": "node"})
    assert_invalid("update_resource", {"target": {"uri": "res://material.tres"}, "set": {}, "scope": "node"})
    tile_change = {"op": "add_physics_layer"}
    assert_valid("edit_tileset", {"target": node_target, "changes": [tile_change], "scope": "node"})
    assert_valid("edit_tileset", {"project": "/tmp/project", "target": node_target, "changes": [tile_change]})
    assert_valid("update_resource", {"project": "/tmp/project", "target": node_target, "set": {}, "scope": "node"})
    assert_invalid("edit_tileset", {"target": {"uri": "res://tileset.tres"}, "changes": [tile_change], "scope": "node"})
    assert_invalid("send_input", {"run_id": "run-1", "events": [
        {"type": "key", "key": "Space", "pressed": True, "at_ms": 60001},
    ]})
    assert "Repair source with edit_script" in SPECS["create_script"]["description"]


def test_resource_selectors_reject_partial_and_mixed_forms_across_tools():
    node = {"scene": "res://main.tscn", "path": "root/Main"}
    selectors = [
        {"uri": "res://material.tres", "node": node},
        {"uri": "res://material.tres", "property": "material"},
        {"uri": "res://material.tres", "node": node, "property": "material"},
        {"node": node}, {"property": "material"}, {},
    ]
    for target in selectors:
        assert_invalid("get_resource", {"target": target})
        assert_invalid("create_script", {"uri": "res://main.gd", "source": "extends Node\n", "material": target})
        assert_invalid("update_resource", {"target": target, "set": {}, "scope": "node"})
        assert_invalid("update_resource", {"target": target, "set": {}, "scope": "shared"})
        assert_invalid("edit_tileset", {"target": target, "changes": [{"op": "add_physics_layer"}], "scope": "node"})
        assert_invalid("edit_tileset", {"target": target, "changes": [{"op": "add_physics_layer"}], "scope": "shared"})

    node_target = {"node": node, "property": "material"}
    uri_target = {"uri": "res://material.tres"}
    assert_valid("create_script", {"uri": "res://main.gd", "source": "extends Node\n", "material": uri_target})
    assert_valid("create_script", {"uri": "res://main.gd", "source": "extends Node\n", "material": node_target})
    for name, changes in [("update_resource", {"set": {}, "scope": "shared"}),
                          ("edit_tileset", {"changes": [{"op": "add_physics_layer"}], "scope": "shared"})]:
        assert_valid(name, {"target": uri_target, **changes})
        assert_valid(name, {"target": node_target, **changes})


def test_diagnostic_timestamp_uses_safe_integer_range():
    entry = {"entries": [{"time_usec": 2_147_483_648, "cursor": 2_147_483_648}],
             "sources": [], "entries_are_history": True, "origin": "editor"}
    Draft202012Validator(SPECS["get_diagnostics"]["outputSchema"]).validate(entry)
    assert_invalid("get_diagnostics", {"since": 9_007_199_254_740_992})
