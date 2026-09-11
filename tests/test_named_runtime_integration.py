"""Named runtime input and condition payloads against headless Godot."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real Godot runtime"
)]


def test_named_input_events_conditions_and_preflight(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    addon = project / "addons" / "godot_mcp"
    addon.mkdir(parents=True)
    source_addon = Path(__file__).parents[1] / "src" / "godot_mcp" / "addon"
    for name in ("runtime.gd", "capture_image.gd", "source_manifest.gd", "codec.gd", "log_buffer.gd", "operation_result.gd"):
        shutil.copy2(source_addon / name, addon / name)
    (project / "project.godot").write_text(
        "config_version=5\n[application]\nconfig/name=\"named runtime\"\nrun/main_scene=\"res://main.tscn\"\n"
    )
    (project / "main.tscn").write_text("[gd_scene load_steps=2 format=3]\n\n[ext_resource path=\"res://main.gd\" type=\"Script\" id=\"1\"]\n\n[node name=\"Main\" type=\"Node\"]\nscript = ExtResource(\"1\")\n")
    (project / "main.gd").write_text(
        "extends Node\n\nsignal ping\n\nfunc _ready() -> void:\n\tpass\n"
    )
    (project / "probe.gd").write_text(
        '''extends SceneTree
const Runtime = preload("res://addons/godot_mcp/runtime.gd")

class Receiver extends Node:
    var seen: Array[String] = []
    var modified := false
    func _input(event: InputEvent) -> void:
        if event is InputEventKey: seen.append("key:%s:%s" % [event.pressed, event.shift_pressed])
        elif event is InputEventMouseButton: seen.append("button:%s:%s" % [event.pressed, event.button_mask])
        elif event is InputEventMouseMotion: seen.append("motion:%s:%s" % [event.position, event.relative])
        elif event is InputEventScreenTouch: seen.append("touch:%s" % event.pressed)
        elif event is InputEventScreenDrag: seen.append("drag:%s" % event.position)
        elif event is InputEventAction: seen.append("action:%s" % event.pressed)

func _initialize() -> void:
    var scene_error := change_scene_to_file("res://main.tscn")
    assert(scene_error == OK)
    await process_frame
    var helper := Runtime.new()
    var receiver := Receiver.new()
    root.add_child(helper)
    root.add_child(receiver)
    InputMap.add_action("named_action")
    await process_frame

    var capture := {"rect": Rect2i(10, 20, 100, 50), "size": Vector2i(100, 50), "original": Vector2i(200, 100), "viewport": Vector2(400, 300)}
    helper.captures["godot://capture"] = capture
    var transformed := await helper.send_input({"capture_uri": "godot://capture", "events": [{"event": {"mouse_motion": {"position": {"x": 50, "y": 25}, "relative": {"x": 5, "y": 4}}}}]})
    assert(transformed.processed == 1)
    assert(receiver.seen[-1] == "motion:(120.0, 135.0):(10.0, 12.0)")

    var batch := await helper.send_input({"events": [
        {"at_ms": 0, "event": {"key": {"key": "Space", "pressed": true, "physical": true, "shift": true}}},
        {"at_ms": 1, "event": {"mouse_button": {"button": "left", "position": {"x": 1, "y": 2}, "pressed": true}}},
        {"at_ms": 2, "event": {"mouse_motion": {"position": {"x": 2, "y": 3}, "relative": {"x": 1, "y": 1}}}},
        {"at_ms": 3, "event": {"touch": {"position": {"x": 3, "y": 4}, "pressed": true, "index": 2}}},
        {"at_ms": 4, "event": {"drag": {"position": {"x": 4, "y": 5}, "relative": {"x": 1, "y": 0}, "index": 2}}},
        {"at_ms": 5, "event": {"action": {"action": "named_action", "pressed": true, "strength": 0.5}}}
    ]})
    assert(batch.processed == 6 and batch.held_inputs == 4)
    assert(receiver.seen.size() >= 8)
    assert(receiver.seen.any(func(item: String) -> bool: return item.begins_with("key:")))
    assert(receiver.seen.any(func(item: String) -> bool: return item.begins_with("button:")))
    assert(receiver.seen.any(func(item: String) -> bool: return item.begins_with("motion:")))
    assert(receiver.seen.any(func(item: String) -> bool: return item.begins_with("touch:")))
    assert(receiver.seen.any(func(item: String) -> bool: return item.begins_with("drag:")))
    assert(receiver.seen.any(func(item: String) -> bool: return item.begins_with("action:")))
    assert(receiver.seen.any(func(item: String) -> bool: return item.begins_with("button:true:1")))
    var released := await helper.send_input({"events": [{"event": {"mouse_button": {"button": "left", "position": {"x": 2, "y": 3}, "pressed": false}}}]})
    assert(released.held_inputs == 3)
    helper.release_input()
    assert(helper.held.size() == 0)

    var before := receiver.seen.size()
    var invalid := await helper.send_input({"events": [
        {"event": {"action": {"action": "named_action", "pressed": false}}},
        {"event": {"unknown": {}}}
    ]})
    assert(invalid.error.code == "INVALID_EVENT" and receiver.seen.size() == before)
    var out_of_order := await helper.send_input({"events": [
        {"at_ms": 2, "event": {"action": {"action": "named_action", "pressed": false}}},
        {"at_ms": 1, "event": {"action": {"action": "named_action", "pressed": false}}}
    ]})
    assert(out_of_order.error.code == "INVALID_SEQUENCE" and receiver.seen.size() == before)

    var main: Node = current_scene
    var node_condition := await helper.wait_condition({"node": {"node": {"run_id": "run-test", "path": "/root/Main"}}}, 20, 5)
    assert(node_condition.satisfied)
    var property_condition := await helper.wait_condition({"property": {"node": {"run_id": "run-test", "path": "/root/Main"}, "property": "process_mode", "value": 0}}, 20, 5)
    assert(property_condition.satisfied)
    var scene_condition := await helper.wait_condition({"scene": {"uri": "res://main.tscn"}}, 20, 5)
    assert(scene_condition.satisfied)
    main.call_deferred("emit_signal", "ping")
    var signal_condition := await helper.wait_condition({"signal": {"node": {"run_id": "run-test", "path": "/root/Main"}, "signal": "ping"}}, 100, 5)
    assert(signal_condition.satisfied)
    print("NAMED_RUNTIME_OK")
    quit(0)
'''
    )
    result = subprocess.run(
        [os.environ.get("GODOT", "godot"), "--headless", "--path", str(project), "--script", "res://probe.gd"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "NAMED_RUNTIME_OK" in result.stdout
