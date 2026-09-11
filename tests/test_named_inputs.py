import pytest
from jsonschema import Draft202012Validator, ValidationError

from godot_mcp.catalog import SPECS


def validate(tool, value):
    Draft202012Validator(SPECS[tool]["inputSchema"]).validate(value)


NODE = {"scene": "res://main.tscn", "path": "Main"}
RUN_NODE = {"run_id": "run-1", "path": "/root/Main"}
POINT = {"x": 1, "y": 2}


@pytest.mark.parametrize("event", [
    {"key": {"key": "Space", "pressed": True}},
    {"mouse_button": {"button": "left", "position": POINT, "pressed": True}},
    {"mouse_motion": {"position": POINT}},
    {"touch": {"position": POINT, "pressed": True}},
    {"drag": {"position": POINT, "relative": {"x": 1, "y": 0}}},
    {"action": {"action": "ui_accept", "pressed": True}},
])
def test_each_input_event_kind_has_named_payload(event):
    validate("send_input", {"run_id": "run-1", "events": [{"at_ms": 10, "event": event}]})


@pytest.mark.parametrize("condition", [
    {"scene": {"uri": "res://main.tscn"}},
    {"node": {"node": RUN_NODE}},
    {"property": {"node": RUN_NODE, "property": "visible", "value": True}},
    {"signal": {"node": RUN_NODE, "signal": "ready"}},
])
def test_each_condition_kind_has_named_payload(condition):
    validate("wait_for_condition", {"run_id": "run-1", "condition": condition})


@pytest.mark.parametrize("change", [
    {"create": {"uri": "res://new.gd", "source": "extends Node"}},
    {"replace": {"uri": "res://a.gd", "if_revision": "r1", "source": "extends Node"}},
    {"edit": {"uri": "res://a.gd", "if_revision": "r1", "edits": [{"range": {"start": {"line": 1, "column": 1}, "end": {"line": 1, "column": 2}}, "text": "x"}]}},
])
def test_each_script_batch_kind_has_named_payload(change):
    validate("apply_script_changes", {"changes": [change]})


def test_edit_script_uses_replace_or_edit_choice():
    validate("edit_script", {"change": {"replace": {"uri": "res://a.gd", "if_revision": "r1", "source": "x"}}})
    validate("edit_script", {"change": {"edit": {"uri": "res://a.gd", "if_revision": "r1", "edits": [{"range": {"start": {"line": 1, "column": 1}, "end": {"line": 1, "column": 2}}, "text": "x"}]}}})


def test_resource_and_scoped_targets():
    validate("get_resource", {"target": {"uri": "res://material.tres"}})
    validate("get_resource", {"target": {"node": {**NODE, "property": "material"}}})
    validate("update_resource", {"target": {"local": {**NODE, "property": "material"}}, "set": {}})
    validate("update_resource", {"target": {"shared": {"uri": "res://material.tres"}}, "set": {}})


def test_node_source_animation_tracks_and_keys():
    for source in ({"class": "Node"}, {"instance": "res://child.tscn"}, {"duplicate": NODE}):
        validate("create_nodes", {"parent": NODE, "nodes": [{"name": "Child", "source": source}]})
    player = {"player": NODE, "name": "A", "tracks": [
        {"add": {"kind": "value", "path": "position", "keys": [{"set": {"time": 0, "value": 1}}, {"remove": {"time": 1}}]}},
        {"update": {"index": 0, "keys": [{"set": {"time": 0, "value": 2}}]}},
        {"remove": {"index": 1}},
    ]}
    validate("edit_animation", player)


@pytest.mark.parametrize("change", [
    {"add_atlas": {"texture": "res://atlas.png"}},
    {"define_tile": {"source": {"id": 0}, "atlas": {"x": 0, "y": 0}}},
    {"remove_tile": {"source": {"key": "atlas"}, "atlas": {"x": 0, "y": 0}}},
    {"add_physics_layer": {}},
    {"collision": {"source": {"id": 0}, "atlas": {"x": 0, "y": 0}, "polygons": []}},
    {"add_terrain_set": {}},
    {"terrain": {"source": {"key": "atlas"}, "atlas": {"x": 0, "y": 0}, "set": {"terrain_set": 0}}},
])
def test_each_tileset_case_has_named_payload(change):
    validate("edit_tileset", {"target": {"shared": {"uri": "res://tileset.tres"}}, "changes": [change]})


@pytest.mark.parametrize("tool,value", [
    ("send_input", {"run_id": "r", "events": [{"event": {}}]}),
    ("send_input", {"run_id": "r", "events": [{"event": {"key": {"key": "A", "pressed": True}, "action": {"action": "jump", "pressed": True}}}]}),
    ("apply_script_changes", {"changes": [{"create": {"uri": "res://a.gd", "source": "x"}, "edit": {"uri": "res://a.gd", "if_revision": "r", "edits": []}}]}),
    ("edit_tileset", {"target": {"shared": {"uri": "res://t.tres"}}, "changes": [{"add_atlas": {"texture": "res://a.png", "unknown": True}}]}),
])
def test_missing_multiple_or_unknown_named_cases_fail(tool, value):
    with pytest.raises(ValidationError):
        validate(tool, value)


@pytest.mark.parametrize("tool,value", [
    ("send_input", {"run_id": "r", "events": [{"event": {"key": "bad"}}]}),
    ("apply_script_changes", {"changes": [{"create": "bad"}]}),
    ("create_nodes", {"parent": NODE, "nodes": [{"name": "N", "source": {"class": 1}}]}),
])
def test_wrong_payload_types_fail(tool, value):
    with pytest.raises(ValidationError):
        validate(tool, value)
