import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real Godot")]

ROOT = Path(__file__).resolve().parents[1]


def run_godot(tmp_path: Path, script: str) -> subprocess.CompletedProcess[str]:
    addon = tmp_path / "addons" / "godot_mcp"
    addon.mkdir(parents=True)
    shutil.copy2(ROOT / "src/godot_mcp/addon/process_output.gd", addon / "process_output.gd")
    shutil.copy2(ROOT / "src/godot_mcp/addon/source_validation.gd", addon / "source_validation.gd")
    (tmp_path / "project.godot").write_text("config_version=5\n")
    (tmp_path / "probe.gd").write_text(script)
    return subprocess.run([os.environ.get("GODOT", "godot"), "--headless", "--path", str(tmp_path), "--script", "res://probe.gd"], capture_output=True, text=True, check=False, timeout=90)


def test_process_output_preserves_all_utf8_boundaries_and_reports_malformed_eof(tmp_path):
    text = "가🙂"
    values = ", ".join(str(value) for value in text.encode())
    script = f'''extends SceneTree
const Collector = preload("res://addons/godot_mcp/process_output.gd")
func _initialize() -> void:
    var original := PackedByteArray([{values}])
    for split: int in original.size() + 1:
        var collector := Collector.new()
        collector.append("stdout", original.slice(0, split))
        collector.append("stdout", original.slice(split))
        if collector.result().stdout != "{text}": quit(1); return
    var malformed := Collector.new()
    malformed.append("stderr", PackedByteArray([226, 130]))
    if not malformed.result().stderr.contains("�"): quit(1); return
    quit(0)
'''
    result = run_godot(tmp_path, script)
    assert result.returncode == 0, result.stdout + result.stderr


def test_process_output_caps_bytes_but_continues_collection(tmp_path):
    script = '''extends SceneTree
const Collector = preload("res://addons/godot_mcp/process_output.gd")
func _initialize() -> void:
    var collector := Collector.new()
    var first := PackedByteArray()
    first.resize(199999)
    first.fill(97)
    collector.append("stdout", first)
    collector.append("stdout", "가".to_utf8_buffer())
    collector.append("stdout", "ignored".to_utf8_buffer())
    var result: Dictionary = collector.result()
    if result.stdout.length() != 199999 or result.stdout.contains("�") or not result.truncated or not result.stdout_truncated or result.stdout_bytes != 200009: quit(1); return
    quit(0)
'''
    result = run_godot(tmp_path, script)
    assert result.returncode == 0, result.stdout + result.stderr


def test_execute_preserves_child_stdout_and_stderr_mapping(tmp_path):
    (tmp_path / "child.gd").write_text(
        '''extends SceneTree
func _initialize() -> void:
    print("CHILD_STDOUT 가🙂")
    printerr("CHILD_STDERR 가🙂")
    quit(0)
'''
    )
    script = '''extends SceneTree
const Validation = preload("res://addons/godot_mcp/source_validation.gd")
func _initialize() -> void:
    var validator := Validation.new(null)
    var args := PackedStringArray(["--headless", "--path", ProjectSettings.globalize_path("res://"), "--script", "res://child.gd"])
    var result: Dictionary = validator._execute(OS.get_executable_path(), args, 5000)
    print("EXECUTED=" + JSON.stringify(result))
    if not result.ok or not str(result.message).contains("CHILD_STDOUT 가🙂") or not str(result.message).contains("CHILD_STDERR 가🙂"): quit(1); return
    quit(0)
'''
    result = run_godot(tmp_path, script)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "EXECUTED=" in result.stdout


def test_snapshot_skips_unrelated_symlink_and_marks_dependent_source(tmp_path):
    outside = tmp_path.parent / "outside-source.gd"
    outside.write_text("extends Node\n")
    (tmp_path / "main.gd").write_text("extends Node\n")
    (tmp_path / "unrelated-link.gd").symlink_to(outside)
    script = '''extends SceneTree
const Validation = preload("res://addons/godot_mcp/source_validation.gd")
func _initialize() -> void:
    var validator := Validation.new(null)
    var manifest: Dictionary = {}
    var excluded: Array[String] = []
    var symlinks: Array[String] = []
    var target := ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir().path_join("snapshot-target")
    var error: String = validator._copy_tree(ProjectSettings.globalize_path("res://"), target, [0, 0], manifest, excluded, symlinks)
    if not error.is_empty() or symlinks != ["unrelated-link.gd"]: quit(1); return
    if not validator._project_changed(ProjectSettings.globalize_path("res://"), manifest, symlinks).is_empty(): quit(1); return
    DirAccess.remove_absolute("res://unrelated-link.gd")
    if not "symlink paths changed" in validator._project_changed(ProjectSettings.globalize_path("res://"), manifest, symlinks): quit(1); return
    if not validator._affected_by_symlink("res://main.gd", "preload(\\"res://unrelated-link.gd\\")", symlinks): quit(1); return
    quit(0)
'''
    result = run_godot(tmp_path, script)
    assert result.returncode == 0, result.stdout + result.stderr


def test_validator_marks_transitive_symlink_dependencies_unavailable(tmp_path):
    """Exercise validator.check's worker path for A -> B -> skipped symlink C."""
    outside = tmp_path.parent / "transitive-outside.gd"
    outside.write_text("extends RefCounted\n")
    (tmp_path / "A.gd").write_text('extends RefCounted\nconst B = preload("res://B.gd")\n')
    (tmp_path / "B.gd").write_text('extends RefCounted\nconst C = preload("res://C.gd")\n')
    (tmp_path / "C.gd").symlink_to(outside)
    (tmp_path / "unrelated.gd").write_text("extends RefCounted\n")
    script = '''extends SceneTree
const Validation = preload("res://addons/godot_mcp/source_validation.gd")
func _initialize() -> void:
    var validator := Validation.new(null)
    var project := ProjectSettings.globalize_path("res://")
    var result: Dictionary = validator._run(project, OS.get_executable_path(), ["res://A.gd", "res://B.gd", "res://unrelated.gd"], {}, {"res://A.gd": "a", "res://B.gd": "b", "res://unrelated.gd": "u"})
    print(JSON.stringify(result))
    for source: Dictionary in result.sources:
        if source.uri in ["res://A.gd", "res://B.gd"] and source.state != "unavailable": quit(1); return
        if source.uri == "res://unrelated.gd" and source.valid != true: quit(2); return
    quit(0)
'''
    result = run_godot(tmp_path, script)
    assert result.returncode == 0, result.stdout + result.stderr
