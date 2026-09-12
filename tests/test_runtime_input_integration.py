"""Focused runtime input regressions against the real Godot runtime."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real Godot runtime"
)]


def test_mouse_mask_and_capture_relative_scaling(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    addon = project / "addons" / "godot_mcp"
    addon.mkdir(parents=True)
    source_addon = Path(__file__).parents[1] / "src" / "godot_mcp" / "addon"
    for name in ("runtime.gd", "capture_image.gd", "source_manifest.gd", "codec.gd", "log_buffer.gd", "operation_result.gd"):
        shutil.copy2(source_addon / name, addon / name)
    (project / "project.godot").write_text("config_version=5\n[application]\nconfig/name=\"input test\"\n")
    (project / "probe.gd").write_text(
        '''extends SceneTree
const Runtime = preload("res://addons/godot_mcp/runtime.gd")
class Observer extends Node:
    var masks: Array[int] = []
    func _input(event: InputEvent) -> void:
        if event is InputEventMouseMotion: masks.append(event.button_mask)
func _initialize() -> void:
    var helper := Runtime.new()
    var observer := Observer.new()
    root.add_child(helper)
    root.add_child(observer)
    await process_frame
    var capture := {"mapping": Transform2D(Vector2(2, 0), Vector2(0, 2), Vector2.ZERO), "viewport": root.get_viewport().get_visible_rect().size, "input_transform": root.get_viewport().get_final_transform()}
    helper.captures["godot://capture"] = capture
    var event: Dictionary = helper.make_event({"event": {"mouse_motion": {"position": {"x": 10, "y": 10}, "relative": {"x": 5, "y": 10}}}}, "godot://capture")
    print("CAPTURE_POSITION=" + str(event.event.position))
    print("CAPTURE_RELATIVE=" + str(event.event.relative))
    await helper.send_input({"events": [
        {"event": {"mouse_button": {"button": "left", "position": {"x": 1, "y": 1}, "pressed": true}}},
        {"event": {"mouse_motion": {"position": {"x": 2, "y": 2}, "relative": {"x": 1, "y": 2}}}},
        {"event": {"mouse_button": {"button": "left", "position": {"x": 2, "y": 2}, "pressed": false}}},
        {"event": {"mouse_motion": {"position": {"x": 3, "y": 3}, "relative": {"x": 1, "y": 2}}}}
    ]})
    print("MASKS=" + str(observer.masks))
    quit()
'''
    )
    result = subprocess.run(
        [os.environ.get("GODOT", "godot"), "--headless", "--path", str(project), "--script", "res://probe.gd"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CAPTURE_POSITION=(20.0, 20.0)" in result.stdout
    assert "CAPTURE_RELATIVE=(10.0, 20.0)" in result.stdout
    assert "MASKS=[1, 0]" in result.stdout


def test_mouse_masks_release_retention_and_capture_transforms(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    addon = project / "addons" / "godot_mcp"
    addon.mkdir(parents=True)
    source_addon = Path(__file__).parents[1] / "src" / "godot_mcp" / "addon"
    for name in ("runtime.gd", "capture_image.gd", "source_manifest.gd", "codec.gd", "log_buffer.gd", "operation_result.gd"):
        shutil.copy2(source_addon / name, addon / name)
    (project / "project.godot").write_text("config_version=5\n[application]\nconfig/name=\"mask test\"\n")
    (project / "probe.gd").write_text(
        '''extends SceneTree
const Runtime = preload("res://addons/godot_mcp/runtime.gd")
class Receiver extends Node:
    signal motion_seen
    var masks: Array[int] = []
    var motions: Array[Vector2] = []
    var relatives: Array[Vector2] = []
    var drags: Array[Vector2] = []
    var drag_relatives: Array[Vector2] = []
    var buttons: Array[int] = []
    var button_masks: Array[int] = []
    var key_presses: Array[bool] = []
    var action_presses: Array[bool] = []
    var touch_presses: Array[bool] = []
    func _input(event: InputEvent) -> void:
        if event is InputEventMouseMotion:
            masks.append(event.button_mask)
            motion_seen.emit()
            motions.append(event.position)
            relatives.append(event.relative)
        elif event is InputEventMouseButton:
            buttons.append(event.button_index if event.pressed else -event.button_index)
            button_masks.append(event.button_mask)
        elif event is InputEventScreenDrag:
            drags.append(event.position)
            drag_relatives.append(event.relative)
        elif event is InputEventKey:
            key_presses.append(event.pressed)
        elif event is InputEventAction:
            action_presses.append(event.pressed)
        elif event is InputEventScreenTouch:
            touch_presses.append(event.pressed)

func _initialize() -> void:
    var helper := Runtime.new()
    var receiver := Receiver.new()
    receiver.name = "Receiver"
    root.add_child(helper)
    root.add_child(receiver)
    await process_frame
    var capture := {"mapping": Transform2D(Vector2(2, 0), Vector2(0, 3), Vector2(20, 60)), "viewport": root.get_viewport().get_visible_rect().size, "input_transform": root.get_viewport().get_final_transform()}
    helper.captures["godot://capture"] = capture
    var batch := await helper.send_input({"capture_uri": "godot://capture",
        "observe": [{"node": {"path": "/root/Receiver"}, "properties": ["masks", "missing"]}],
        "wait_for": {"signal": {"node": {"path": "/root/Receiver"}, "signal": "motion_seen"}}, "events": [
        {"event": {"mouse_button": {"button": "left", "position": {"x": 1, "y": 1}, "pressed": true}}},
        {"event": {"mouse_motion": {"position": {"x": 50, "y": 25}, "relative": {"x": 5, "y": 4}}}},
        {"event": {"mouse_button": {"button": "right", "position": {"x": 50, "y": 25}, "pressed": true}}},
        {"event": {"mouse_motion": {"position": {"x": 50, "y": 25}, "relative": {"x": 5, "y": 4}}}},
        {"event": {"mouse_button": {"button": "left", "position": {"x": 50, "y": 25}, "pressed": false}}},
        {"event": {"mouse_motion": {"position": {"x": 50, "y": 25}, "relative": {"x": 5, "y": 4}}}},
        {"event": {"mouse_button": {"button": "right", "position": {"x": 50, "y": 25}, "pressed": false}}},
        {"event": {"mouse_motion": {"position": {"x": 50, "y": 25}, "relative": {"x": 5, "y": 4}}}}
    ]})
    assert(batch.processed == 8 and batch.held_inputs == 0)
    assert(batch.injections.size() == 8)
    for injection: Dictionary in batch.injections:
        assert(injection.frame == batch.injections[0].frame)
    assert(batch.observations.before[0].properties.masks == [])
    assert(batch.observations.after[0].properties.masks == [1, 3, 2, 0])
    assert(batch.observations.after[0].unavailable_properties == ["missing"])
    assert(batch.observations.before[0].observed_at_usec <= batch.injections[0].injected_at_usec)
    assert(batch.condition.satisfied and batch.condition.satisfied_at_usec >= batch.injections[0].injected_at_usec)
    assert(batch.condition.satisfied_at_usec <= batch.condition.observed_at_usec)
    assert(batch.condition.observed_at_usec <= batch.observations.after[0].observed_at_usec)
    assert(receiver.masks == [1, 3, 2, 0])
    assert(receiver.motions[0] == Vector2(120, 135) and receiver.relatives[0] == Vector2(10, 12))
    var pressed := await helper.send_input({"events": [{"event": {"mouse_button": {"button": "left", "pressed": true}}}]})
    assert(pressed.held_inputs == 1)
    var during := await helper.send_input({"events": [{"event": {"mouse_motion": {"position": {"x": 2, "y": 3}, "relative": {"x": 1, "y": 1}}}}]})
    assert(during.held_inputs == 1 and receiver.masks[-1] == 1)
    var held_wheel := await helper.send_input({"events": [{"event": {"mouse_button": {"button": "wheel_up", "position": {"x": 2, "y": 3}, "pressed": true}}}]})
    assert(held_wheel.held_inputs == 1 and receiver.button_masks[-1] == 1)
    var released := await helper.send_input({"events": [{"event": {"mouse_button": {"button": "left", "pressed": false}}}]})
    assert(released.held_inputs == 0)
    await helper.send_input({"events": [{"event": {"mouse_motion": {"position": {"x": 2, "y": 3}, "relative": {"x": 1, "y": 1}}}}]})
    assert(receiver.masks[-1] == 0)
    var wheel := await helper.send_input({"events": [{"event": {"mouse_button": {"button": "wheel_up", "pressed": true}}}]})
    assert(wheel.held_inputs == 0)
    InputMap.add_action("release_action")
    receiver.key_presses.clear()
    receiver.action_presses.clear()
    receiver.touch_presses.clear()
    var auto_release := await helper.send_input({"events": [
        {"event": {"key": {"key": "Space", "pressed": true}}},
        {"event": {"action": {"action": "release_action", "pressed": true}}},
        {"event": {"touch": {"index": 7, "position": {"x": 1, "y": 2}, "pressed": true}}}
    ], "release_after": true})
    assert(auto_release.held_inputs == 0)
    assert(receiver.key_presses == [true, false] and receiver.action_presses == [true, false] and receiver.touch_presses == [true, false])
    assert(Input.is_key_pressed(KEY_SPACE) == false and Input.is_action_pressed("release_action") == false)
    var drag := await helper.send_input({"capture_uri": "godot://capture", "events": [{"event": {"drag": {"position": {"x": 50, "y": 25}, "relative": {"x": 5, "y": 4}, "pressed": true}}}]})
    assert(drag.processed == 1 and receiver.drags[-1] == Vector2(120, 135) and receiver.drag_relatives[-1] == Vector2(10, 12))

    root.size = Vector2i(1280, 800)
    root.content_scale_size = Vector2i(1440, 900)
    root.content_scale_mode = Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
    await process_frame
    await process_frame
    var before_stale := receiver.motions.size()
    var stale := await helper.send_input({"capture_uri": "godot://capture", "events": [{"event": {"mouse_motion": {"position": {"x": 50, "y": 25}, "relative": {"x": 5, "y": 4}}}}]})
    assert(stale.error.code == "STALE_CAPTURE" and receiver.motions.size() == before_stale)
    var stretched := await helper.send_input({"events": [{"event": {"mouse_motion": {"position": {"x": 720, "y": 450}, "relative": {"x": 0, "y": 0}}}}]})
    assert(stretched.processed == 1 and receiver.motions[-1].is_equal_approx(Vector2(720, 450)))
    print("MASK_RELEASE_CAPTURE_OK")
    quit()
'''
    )
    result = subprocess.run(
        [os.environ.get("GODOT", "godot"), "--headless", "--path", str(project), "--script", "res://probe.gd"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "MASK_RELEASE_CAPTURE_OK" in result.stdout
