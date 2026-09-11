"""Timeout responses retain exact import ownership until safe undo registration."""
from __future__ import annotations

import asyncio
import os

import pytest
from jsonschema import Draft202012Validator
from mcp import Client

from godot_mcp.bridge import ToolError
from godot_mcp.catalog import SPECS
from godot_mcp.server import create_server

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get('GODOT_MCP_INTEGRATION') != '1', reason='opt-in real editor')]


def prepare_timeout_probe(project):
    plugin = project / 'addons/godot_mcp/plugin.gd'
    source = plugin.read_text()
    signature = 'func dispatch(method: String, p: Dictionary) -> Dictionary:\n'
    source = source.replace(signature, signature + '\tif method == "_test_import_wait":\n\t\tassets.test_pending_phase = str(p.get("phase", ""))\n\t\treturn {"phase": assets.test_pending_phase}\n')
    plugin.write_text(source)
    assets = project / 'addons/godot_mcp/assets.gd'
    source = assets.read_text().replace('var host: EditorPlugin\n', 'var host: EditorPlugin\nvar test_pending_phase: String = ""\n')
    signature = 'func wait_import(timeout_ms: int = 30000) -> bool:\n'
    assert signature in source
    source = source.replace(signature, signature + '''
	if not test_pending_phase.is_empty():
		for job: Dictionary in imports.operations.values():
			if job.phase == test_pending_phase and not job.done:
				await host.get_tree().process_frame
				return false
''')
    assets.write_text(source)


async def completed(bridge, operation_id):
    for _ in range(200):
        try:
            result = await bridge.call('get_context', {'scope': 'operations', 'operation_id': operation_id})
            operation = result['operations'][0]
            if operation['phase'] in {'completed', 'failed'}:
                return operation
        except ToolError as error:
            if error.code != 'EDITOR_BUSY':
                raise
        await asyncio.sleep(.05)
    pytest.fail('Import did not finish after releasing the controlled wait')


def prepare_partial_write_probe(project):
    prepare_timeout_probe(project)
    assets = project / 'addons/godot_mcp/assets.gd'
    source = assets.read_text().replace('var test_pending_phase: String = ""\n',
                                        'var test_pending_phase: String = ""\nvar test_fail_write: bool = true\n')
    signature = '\t\tfile.store_buffer(files[path])\n'
    assert signature in source
    source = source.replace(signature, '''
		if test_fail_write:
			test_fail_write = false
			file.store_buffer(files[path].slice(0, 20))
			file.close()
			return false
''' + signature)
    assets.write_text(source)


@pytest.mark.parametrize('editor', [prepare_timeout_probe], indirect=True)
@pytest.mark.parametrize('phase', ['importing', 'reimporting'])
async def test_import_timeout_retains_changes_finishes_and_undoes(editor, phase):
    bridge, tmp = editor
    source = tmp / 'source.svg'
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="#138cf2"/></svg>')
    destination = 'res://art/source.svg'
    spec = {'source': source.as_uri(), 'destination': destination,
            'options': {'mipmaps/generate': True}}
    await bridge.call('_test_import_wait', {'phase': phase})
    async with Client(create_server(bridge.project, bridge)) as client:
        response = await client.call_tool('import_assets', {'files': [spec]})
        result = response.structured_content
        assert response.is_error, result
        Draft202012Validator(SPECS['import_assets']['outputSchema']).validate(result)
        assert result['status'] == 'partial' and not result['complete'], result
        assert result['phase'] == phase and result['pending'] == [phase]
        assert result['files_written'] == [destination]
        assert result['undo_state'] == 'pending' and result['edit_id'] is None
        assert result['failures'][0]['code'] == 'IMPORT_TIMEOUT'
        assert (bridge.project / 'art/source.svg').read_bytes() == source.read_bytes()
        if phase == 'reimporting':
            assert result['options_changed'] == [destination + '.import'], result
            assert 'mipmaps/generate=true' in (bridge.project / 'art/source.svg.import').read_text()
        else:
            assert result['options_changed'] == []
        with pytest.raises(ToolError) as duplicate:
            await bridge.call('import_assets', {'files': [spec]})
        assert duplicate.value.code == 'OPERATION_PENDING'
        assert duplicate.value.details['operation_id'] == result['operation_id']
        state = await client.call_tool('get_context', {'scope': 'operations', 'operation_id': result['operation_id']})
        assert state.structured_content['operations'][0]['undo_state'] == 'pending'
        await bridge.call('_test_import_wait', {'phase': ''})
        finished = await completed(bridge, result['operation_id'])
        Draft202012Validator(SPECS['import_assets']['outputSchema']).validate(finished)
        assert finished['status'] == 'completed' and finished['complete'], finished
        assert finished['undo_state'] == 'available' and finished['edit_id']
        assert finished['options_changed'] == [destination + '.import']
        assert finished['assets'][0]['imported']
        if phase == 'importing':
            path = bridge.project / 'art/source.svg'
            finalized = path.read_bytes()
            path.write_bytes(b'external change after import')
            with pytest.raises(ToolError) as conflict:
                await bridge.call('undo_edit', {'edit_id': finished['edit_id']})
            assert conflict.value.code == 'EDIT_CONFLICT'
            assert path.read_bytes() == b'external change after import'
            path.write_bytes(finalized)
        await bridge.call('undo_edit', {'edit_id': finished['edit_id']})
        assert not (bridge.project / 'art/source.svg').exists()
        assert not (bridge.project / 'art/source.svg.import').exists()


@pytest.mark.parametrize('editor', [prepare_timeout_probe], indirect=True)
async def test_external_source_change_during_pending_import_blocks_continuation(editor):
    bridge, tmp = editor
    source = tmp / 'source.svg'
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"/>')
    await bridge.call('_test_import_wait', {'phase': 'importing'})
    result = await bridge.call('import_assets', {'files': [{'source': source.as_uri(), 'destination': 'res://source.svg'}]})
    external = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"/>'
    (bridge.project / 'source.svg').write_text(external)
    await bridge.call('_test_import_wait', {'phase': ''})
    finished = await completed(bridge, result['operation_id'])
    assert finished['status'] == 'partial' and not finished['complete'], finished
    assert finished['undo_state'] == 'unavailable' and finished['edit_id'] is None
    assert finished['failures'][0]['code'] == 'IMPORT_CONFLICT'
    assert (bridge.project / 'source.svg').read_text() == external


@pytest.mark.parametrize('editor', [prepare_partial_write_probe], indirect=True)
@pytest.mark.parametrize('external_change', [False, True])
async def test_partial_write_keeps_a_guarded_recovery_boundary(editor, external_change):
    bridge, tmp = editor
    source = tmp / 'source.svg'
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"/>')
    await bridge.call('_test_import_wait', {'phase': 'settling'})
    result = await bridge.call('import_assets', {'files': [
        {'source': source.as_uri(), 'destination': 'res://partial.svg'},
    ]})
    path = bridge.project / 'partial.svg'
    assert path.read_bytes() == source.read_bytes()[:20]
    assert result['phase'] == 'settling' and result['undo_state'] == 'pending'
    assert result['files_written'] == ['res://partial.svg']
    assert result['failures'][0]['code'] == 'IMPORT_FAILED'
    if external_change:
        path.write_bytes(b'external author content')
    await bridge.call('_test_import_wait', {'phase': ''})
    finished = await completed(bridge, result['operation_id'])
    Draft202012Validator(SPECS['import_assets']['outputSchema']).validate(finished)
    assert finished['status'] == 'partial' and not finished['complete']
    if external_change:
        assert finished['undo_state'] == 'unavailable' and finished['edit_id'] is None
        assert any(f['code'] == 'IMPORT_CONFLICT' for f in finished['failures'])
        assert path.read_bytes() == b'external author content'
    else:
        assert finished['undo_state'] == 'available' and finished['edit_id']
        await bridge.call('undo_edit', {'edit_id': finished['edit_id']})
        assert not path.exists()


async def test_import_rejects_an_unsaved_store_draft(editor):
    bridge, tmp = editor
    draft = 'extends Node\n# unsaved MCP draft\n'
    created = await bridge.call('apply_script_changes', {'changes': [
        {'uri': 'res://draft.gd', 'create': True, 'source': draft},
    ]})
    assert not created['saved']
    assert not (bridge.project / 'draft.gd').exists()
    source = tmp / 'replacement.gd'
    source.write_text('extends Node\n# imported replacement\n')
    with pytest.raises(ToolError) as error:
        await bridge.call('import_assets', {'files': [
            {'source': source.as_uri(), 'destination': 'res://draft.gd'},
        ]})
    assert error.value.code == 'UNSAVED_DOCUMENTS'
    assert not (bridge.project / 'draft.gd').exists()
    current = await bridge.call('read_script', {'uri': 'res://draft.gd'})
    assert current['source'] == draft
