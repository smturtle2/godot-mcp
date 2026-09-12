import pytest
from jsonschema import ValidationError

from godot_mcp.catalog import SPECS


def validate(tool, value):
    from jsonschema import Draft202012Validator
    Draft202012Validator(SPECS[tool]["inputSchema"]).validate(value)


REV = "a" * 64
REF = {"scene": "res://main.tscn", "path": "Main"}


def test_read_scripts_requires_nonempty_documents_and_rejects_legacy_forms():
    validate("read_scripts", {"documents": [{"uri": "res://main.gd"}]})
    with pytest.raises(ValidationError):
        validate("read_scripts", {"documents": []})
    with pytest.raises(ValidationError):
        validate("read_scripts", {"uri": "res://main.gd"})


def test_apply_script_changes_current_inputs_and_revision_hashes():
    validate("apply_script_changes", {"patch": "*** Begin Patch\n*** End Patch"})
    validate("apply_script_changes", {"patch": "x", "base_revisions": {"res://main.gd": REV},
                                       "save": True, "preview": True, "wait_ms": 15000})
    with pytest.raises(ValidationError):
        validate("apply_script_changes", {"patch": "x", "base_revisions": {"res://main.gd": "r1"}})
    with pytest.raises(ValidationError):
        validate("apply_script_changes", {"patch": "x", "wait_ms": 15001})
    with pytest.raises(ValidationError):
        validate("apply_script_changes", {"patch": "x", "changes": []})


def test_resume_script_changes_requires_operation_and_bounded_revisions():
    validate("resume_script_changes", {"operation_id": "op", "revisions": {"res://main.gd": REV}, "wait_ms": 0})
    with pytest.raises(ValidationError):
        validate("resume_script_changes", {"operation_id": "op", "revisions": {}, "wait_ms": 15001})


@pytest.mark.parametrize("attachment", [
    {"script": {"uri": "res://main.gd", "node": REF}},
    {"shader": {"uri": "res://main.gdshader", "target": {"local": {**REF, "property": "material"}}}},
    {"shader": {"uri": "res://main.gdshader", "target": {"shared": {"uri": "res://mat.tres"}}}},
])
def test_script_and_shader_attachments_have_required_scopes(attachment):
    validate("apply_script_changes", {"patch": "x", "attachments": [attachment]})


def test_attachment_selectors_and_diagnostic_log_contracts_are_strict():
    with pytest.raises(ValidationError):
        validate("apply_script_changes", {"patch": "x", "attachments": [{"script": {"uri": "res://a.gd", "node": REF}, "shader": {}}]})
    with pytest.raises(ValidationError):
        validate("apply_script_changes", {"patch": "x", "attachments": [{"shader": {"uri": "res://a.gd", "target": {"local": {**REF, "property": "m"}, "shared": {"uri": "res://m.tres"}}}}]})
    validate("get_diagnostics", {})
    validate("get_diagnostics", {"uris": ["res://a.gd"], "kinds": ["error"]})
    validate("get_logs", {"run_id": "run", "since": 0, "limit": 1})
    with pytest.raises(ValidationError):
        validate("get_diagnostics", {"since": 1})
    with pytest.raises(ValidationError):
        validate("get_logs", {"uris": ["res://a.gd"]})


def test_run_scene_uses_save_uris_and_revision_guards():
    validate("run_scene", {"scene": "res://main.tscn", "save_uris": ["res://main.gd"], "revisions": {"res://main.gd": REV}})
    with pytest.raises(ValidationError):
        validate("run_scene", {"scene": "res://main.tscn", "save": True})


def test_removed_script_tools_are_not_published():
    assert "create_script" not in SPECS
    assert "edit_script" not in SPECS
    assert "read_script" not in SPECS


def test_client_defaults_preserve_read_bases_and_run_identity():
    from godot_mcp.client_state import ClientState

    client, other = ClientState(), ClientState()
    project = '/project'
    client.observe(project, 'read_scripts', {'editor_epoch': 'editor-1', 'documents': [
        {'uri': 'res://main.gd', 'revision': 'read-revision'}]})
    patch = {'patch': '*** Begin Patch\n*** Update File: res://main.gd\n@@\n-old\n+new\n*** End Patch'}
    client.observe(project, 'get_operation_result', {'documents': [{'uri': 'res://main.gd', 'revision': 'late-revision'}]})
    assert client.prepare(project, 'apply_script_changes', patch)['base_revisions'] == {'res://main.gd': 'read-revision'}
    assert other.prepare(project, 'apply_script_changes', patch)['base_revisions'] == {}
    explicit = {**patch, 'base_revisions': {'res://main.gd': 'explicit'}}
    assert client.prepare(project, 'apply_script_changes', explicit)['base_revisions'] == explicit['base_revisions']
    client.observe(project, 'run_scene', {'run_id': 'run-1'})
    args = client.prepare(project, 'send_input', {'events': [], 'observe': [{'node': {'path': '/root/Main'}, 'properties': ['health']}]})
    assert args['run_id'] == args['observe'][0]['node']['run_id'] == 'run-1'
    assert client.prepare(project, 'stop_game', {'run_id': 'explicit-run'})['run_id'] == 'explicit-run'
    client.observe(project, 'get_context', {'editor_epoch': 'editor-2'})
    assert client.prepare(project, 'apply_script_changes', patch)['base_revisions'] == {}
