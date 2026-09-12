from jsonschema import Draft202012Validator

from godot_mcp.catalog import SPECS, TOOL_SPECS


def validator(name):
    return Draft202012Validator(SPECS[name]["inputSchema"])


def assert_valid(name, value):
    errors = list(validator(name).iter_errors(value))
    assert not errors, errors


def assert_invalid(name, value):
    assert list(validator(name).iter_errors(value)), f"unexpectedly accepted: {value!r}"


def test_catalog_has_50_unique_tools_and_valid_json_schemas():
    names = [spec["name"] for spec in TOOL_SPECS]
    assert len(names) == 50
    assert len(set(names)) == 50
    assert set(names) == set(SPECS)
    for spec in TOOL_SPECS:
        assert spec["inputSchema"]["type"] == "object"
        assert spec["inputSchema"]["additionalProperties"] is False
        Draft202012Validator.check_schema(spec["inputSchema"])
        if "outputSchema" in spec:
            Draft202012Validator.check_schema(spec["outputSchema"])


def test_representative_nested_scene_and_animation_inputs_validate():
    assert_valid("get_scene", {
        "project": "/tmp/project", "scene": "res://main.tscn", "path": "Main",
        "properties": ["position"], "include": ["properties", "layout"], "depth": 1,
    })
    assert_valid("edit_animation_graph", {
        "tree": {"scene": "res://main.tscn", "path": "Main/AnimationTree"},
        "root_type": "blend_tree", "states": [{"name": "walk", "animation": "walk"}],
        "nodes": [{"name": "speed", "kind": "blend_space_1d"}],
        "connections": [{"to": "output", "input": 0, "from": "speed"}],
    })


def test_unknown_args_traversal_invalid_revision_and_duration_are_rejected():
    assert_invalid("get_context", {"scope": "all", "unexpected": True})
    assert_invalid("apply_script_changes", {"patch": "x", "changes": []})
    assert_invalid("wait_for_condition", {"run_id": "r", "condition": {"scene": {"uri": "res://main.tscn"}}, "timeout_ms": -1})
    assert_invalid("export_build", {"preset": "linux", "output": "file:///tmp/a", "timeout_ms": -1})
    assert_invalid("send_input", {"run_id": "r", "events": [{"at_ms": 60001, "event": {"key": {"key": "A", "pressed": True}}}]})


def test_project_is_optional_on_editor_tools_when_other_inputs_are_valid():
    assert_valid("get_scene", {"project": "/tmp/project", "scene": "res://main.tscn"})
    assert_valid("get_context", {"project": "/tmp/project", "scope": "editor"})
    assert_valid("update_settings", {"project": "/tmp/project", "settings": {"application/config/name": "Demo"}})


def test_get_scene_include_and_update_settings_event_kinds():
    assert_valid("get_scene", {"include": ["properties", "overrides", "connections", "layout"], "properties": []})
    assert_invalid("get_scene", {"include": ["unknown"]})
    assert_valid("update_settings", {"input_actions": [{
        "name": "move", "events": [
            {"type": "key"}, {"type": "mouse_button"},
            {"type": "joypad_button"}, {"type": "joypad_motion"},
        ],
    }]})


def test_named_choice_contracts_expose_structural_cardinality():
    for name, field, choices in [
        ("send_input", "event", {"key", "mouse_button", "mouse_motion", "touch", "drag", "action"}),
        ("wait_for_condition", "condition", {"scene", "node", "property", "signal"}),
        ("create_nodes", "source", {"class", "instance", "duplicate"}),
        ("edit_animation", "tracks", {"add", "update", "remove"}),
        ("edit_tileset", "changes", {"add_atlas", "define_tile", "remove_tile", "add_physics_layer", "collision", "add_terrain_set", "terrain"}),
    ]:
        schema = SPECS[name]["inputSchema"]
        if name == "send_input":
            item = schema["properties"]["events"]["items"]["properties"][field]
        elif name == "create_nodes":
            item = schema["properties"]["nodes"]["items"]["properties"][field]
        elif name in {"edit_animation", "edit_tileset"}:
            item = schema["properties"][field]["items"]
        else:
            item = schema["properties"][field]
        assert item["minProperties"] == item["maxProperties"] == 1
        assert set(item["properties"]) == choices
        assert item["additionalProperties"] is False


def test_output_contracts_remain_explicit_unions_with_required_fields():
    for name in ("resume_script_changes", "save_documents", "send_input"):
        output = SPECS[name]["outputSchema"]
        assert output["type"] == "object"
        assert len(output["oneOf"]) == 2
        assert output["oneOf"][0]["required"]
        assert output["oneOf"][1]["required"] == ["error"]
    patch_output = SPECS["apply_script_changes"]["outputSchema"]
    assert len(patch_output["oneOf"]) == 3
    assert patch_output["oneOf"][0]["required"]
    assert patch_output["oneOf"][1]["required"] == ["error"]


def test_diagnostic_timestamps_use_safe_integer_range():
    entry = {"entries": [{"time_usec": 2_147_483_648, "cursor": 2_147_483_648}],
             "sources": [], "entries_are_history": True, "origin": "editor"}
    Draft202012Validator(SPECS["get_logs"]["outputSchema"]).validate({
        "entries": entry["entries"], "history": True, "current_verdict": False, "origin": "editor",
    })
    assert_invalid("get_logs", {"since": 9_007_199_254_740_992})
