import pytest
from jsonschema import Draft202012Validator

from godot_mcp.bridge import ToolError
from godot_mcp.catalog import SPECS
from godot_mcp.input_validation import validate_arguments


def rejects(tool, arguments):
    with pytest.raises(ToolError) as caught:
        validate_arguments(Draft202012Validator(SPECS[tool]["inputSchema"]), arguments)
    return caught.value


def test_validation_reports_useful_paths_for_discriminated_inputs():
    error = rejects("send_input", {"run_id": "run-1", "events": [{"event": {"key": {"pressed": True}}}]})
    assert error.details["path"] == ["events", 0, "event", "key", "key"]
    assert "key" in error.details["required"]

    error = rejects("send_input", {"run_id": "run-1", "events": [{"event": {"key": {"key": "Space", "pressed": True, "wrong": True}}}]})
    assert error.details["path"] == ["events", 0, "event", "key", "wrong"]

    error = rejects("send_input", {"run_id": "run-1", "events": [{"event": {}}]})
    assert error.details["path"] == ["events", 0, "event"]
    assert error.details["choices"] == ["key", "mouse_button", "mouse_motion", "touch", "drag", "action"]

    error = rejects("send_input", {"run_id": "run-1", "events": [{"event": {"key": {"key": "Space", "pressed": True}}}], "wait_for": {"node": {"node": {"run_id": "run-1"}}}})
    assert error.details["path"] == ["wait_for", "node", "node", "path"]


def test_validation_reports_resource_alternatives_without_echoing_large_values():
    error = rejects("get_resource", {"target": {"uri": "res://a.tres", "node": {"scene": "res://main.tscn", "path": "Main", "property": "material"}}})
    assert error.details["path"] == ["target"]
    assert error.details["choices"] == ["uri", "node"]

    huge = "x" * 100_000
    error = rejects("get_resource", {"target": {"uri": huge, "node": {"scene": "res://main.tscn", "path": "Main", "property": "material"}}})
    assert len(str(error)) < 2_000
    assert huge not in str(error)


def test_property_map_limits_are_not_reported_as_named_choices():
    error = rejects("update_resource", {"target": {"shared": {"uri": "res://a.tres"}}, "set": {str(i): i for i in range(201)}})
    assert error.details["expected"] == 200
    assert "choices" not in error.details
