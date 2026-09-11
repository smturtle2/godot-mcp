"""Real editor buffer changes must share the source store's save baseline."""
from __future__ import annotations

import hashlib
import os

import pytest

from godot_mcp.bridge import ToolError
from godot_mcp.source_tools import SourceTools

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get('GODOT_MCP_INTEGRATION') != '1', reason='opt-in real editor')]

PROBE = '''
func _test_source_buffer(p: Dictionary) -> Dictionary:
	var uri: String = p.uri
	var editor := EditorInterface.get_script_editor()
	if p.action == "open":
		EditorInterface.edit_script(resource_uri(uri) as Script)
		await get_tree().process_frame
	var buffer: TextEdit = documents.script_buffer(uri)
	if not buffer: return fail("NO_BUFFER", "Expected a real ScriptEditor TextEdit.")
	match p.action:
		"edit":
			buffer.begin_complex_operation()
			buffer.select_all()
			buffer.insert_text_at_caret(p.source)
			buffer.deselect()
			buffer.end_complex_operation()
		"undo": buffer.undo()
		"ui_save": editor.save_all_scripts()
		"restart_observer":
			documents.store.shutdown()
			documents.store = load("res://addons/godot_mcp/source_store.gd").new(self)
			documents.store.observe_open_buffers()
	await get_tree().process_frame
	return {"source": buffer.text, "version": buffer.get_version(), "saved_version": buffer.get_saved_version()}
'''


def prepare_probe(project):
    plugin = project / 'addons/godot_mcp/plugin.gd'
    source = plugin.read_text()
    signature = 'func dispatch(method: String, p: Dictionary) -> Dictionary:\n'
    assert source.count(signature) == 1
    source = source.replace(signature, signature + '\tif method == "_test_source_buffer": return await _test_source_buffer(p)\n')
    plugin.write_text(source + PROBE)


URI = 'res://manual.gd'
BASE = 'extends Node\nvar number: int = 1\n'
EDITED = 'extends Node\nvar number: int = 2\n'
EXTERNAL = 'extends Node\nvar number: int = 3\n'


async def setup_buffer(bridge):
    source_tools = SourceTools(bridge)
    receipt = await source_tools.call('apply_script_changes', {
        'patch': '*** Begin Patch\n*** Add File: res://manual.gd\n+extends Node\n+var number: int = 1\n*** End Patch',
        'save': True,
        'wait_ms': 0,
    })
    detail = await source_tools.operation(receipt['operation_id'], 60000)
    result = detail['result']
    assert result['status'] == 'completed' and result['documents'][0]['save']['state'] == 'saved', result
    await bridge.call('_test_source_buffer', {'uri': URI, 'action': 'open'})


@pytest.mark.parametrize('editor', [prepare_probe], indirect=True)
async def test_manual_edit_conflict_blocks_source_and_scene_save(editor):
    bridge, _ = editor
    await setup_buffer(bridge)
    await bridge.call('_test_source_buffer', {'uri': URI, 'action': 'edit', 'source': EDITED})
    path = bridge.project / 'manual.gd'
    path.write_text(EXTERNAL)
    info = (await bridge.call('read_scripts', {'documents': [{'uri': URI}]}))['documents'][0]
    assert info['source'] == EDITED and info['external_change'], info
    assert info['base_disk_revision'] == hashlib.sha256(BASE.encode()).hexdigest()
    assert info['baseline_known'] and info['conflict'] == 'external_change'
    saved = await bridge.call('save_documents', {'uris': [URI]})
    assert saved['status'] == 'failed' and not saved['complete'] and saved['documents'][0]['save']['state'] == 'failed', saved
    assert path.read_text() == EXTERNAL
    scene = bridge.project / 'main.tscn'
    scene_before = scene.read_bytes()
    with pytest.raises(ToolError) as error:
        await bridge.call('save_documents', {'uris': ['res://main.tscn']})
    assert error.value.code == 'SAVE_SCOPE_REQUIRED'
    assert URI in error.value.details['save_plan']['additional_uris'], error.value.details
    saved_scene = await bridge.call('save_documents', {'uris': [URI, 'res://main.tscn']})
    assert saved_scene['status'] == 'failed' and not saved_scene['complete'] and saved_scene['failures'][0]['details']['conflicts'], saved_scene
    assert scene.read_bytes() == scene_before and path.read_text() == EXTERNAL


@pytest.mark.parametrize('editor', [prepare_probe], indirect=True)
async def test_already_dirty_buffer_requires_known_baseline_and_undo_reconciles(editor):
    bridge, _ = editor
    await setup_buffer(bridge)
    await bridge.call('_test_source_buffer', {'uri': URI, 'action': 'edit', 'source': EDITED})
    await bridge.call('_test_source_buffer', {'uri': URI, 'action': 'restart_observer'})
    info = (await bridge.call('read_scripts', {'documents': [{'uri': URI}]}))['documents'][0]
    assert not info['baseline_known'] and info['conflict'] == 'baseline_unknown', info
    saved = await bridge.call('save_documents', {'uris': [URI]})
    assert saved['status'] == 'failed' and not saved['complete'] and saved['documents'][0]['save']['state'] == 'failed'
    assert (bridge.project / 'manual.gd').read_text() == BASE
    await bridge.call('_test_source_buffer', {'uri': URI, 'action': 'undo'})
    info = (await bridge.call('read_scripts', {'documents': [{'uri': URI}]}))['documents'][0]
    assert info['source'] == BASE and not info['external_change'] and not info['unsaved'], info


@pytest.mark.parametrize('editor', [prepare_probe], indirect=True)
async def test_ui_save_updates_baseline_before_next_manual_change(editor):
    bridge, _ = editor
    await setup_buffer(bridge)
    await bridge.call('_test_source_buffer', {'uri': URI, 'action': 'edit', 'source': EDITED})
    await bridge.call('_test_source_buffer', {'uri': URI, 'action': 'ui_save'})
    assert (bridge.project / 'manual.gd').read_text() == EDITED
    await bridge.call('_test_source_buffer', {'uri': URI, 'action': 'edit', 'source': 'extends Node\nvar number: int = 4\n'})
    (bridge.project / 'manual.gd').write_text(EXTERNAL)
    info = (await bridge.call('read_scripts', {'documents': [{'uri': URI}]}))['documents'][0]
    assert info['external_change'], info
    assert info['base_disk_revision'] == hashlib.sha256(EDITED.encode()).hexdigest(), info
