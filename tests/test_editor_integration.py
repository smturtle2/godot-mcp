"""Real editor acceptance: no mocked Godot APIs. Opt in with GODOT_MCP_INTEGRATION=1."""
from __future__ import annotations

import asyncio
import base64
import os
import subprocess

import pytest
from mcp import Client

from godot_mcp.bridge import ToolError
from godot_mcp.catalog import TOOL_SPECS
from godot_mcp.debugger import DebugTools
from godot_mcp.server import create_server
from godot_mcp.source_tools import SourceTools

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get('GODOT_MCP_INTEGRATION') != '1', reason='opt-in real editor')]


def ref(path='.', scene='res://main.tscn'):
    return {'scene': scene, 'path': path}


def vector(x, y):
    return {'$type': 'Vector2', 'x': x, 'y': y}


async def call(bridge, tool_name, **arguments):
    if tool_name == 'apply_script_changes':
        source_tools = SourceTools(bridge)
        arguments['wait_ms'] = 0
        receipt = await source_tools.call(tool_name, arguments)
        detail = await source_tools.operation(receipt['operation_id'], 60000)
        result = detail['result']
    else:
        result = await bridge.call(tool_name, arguments)
    assert result, f'{tool_name} returned empty (check GDScript runtime errors)'
    return result


async def test_editor_authoring(editor):
    b, tmp = editor
    server = create_server(b.project, b)
    async with Client(server) as client:
        assert len((await client.list_tools()).tools) == len(TOOL_SPECS)
        result = await client.call_tool('get_context', {})
        assert not result.is_error
    logs = await call(b, 'get_logs')
    assert not any('Unexpected NUL character' in entry['message'] for entry in logs['entries']), logs
    r = await call(b, 'create_nodes', parent=ref(), nodes=[{'name': n, 'source': {'class': c}} for n, c in [('Sprite', 'Sprite2D'), ('Anim', 'AnimationPlayer'), ('Tree', 'AnimationTree'), ('Tiles', 'TileMapLayer')]])
    assert len(r['nodes']) == 4
    r = await call(b, 'update_nodes', changes=[{'node': ref('Sprite'), 'set': {'position': vector(12, 34)}}])
    assert r['nodes'][0]['properties']['position']['x'] == 12
    await call(b, 'undo_edit', edit_id=r['edit_id'])
    scene = await call(b, 'get_scene', properties=['position'])
    assert scene['root']['children'][0]['properties']['position']['x'] == 0
    assert scene['unsaved']
    assert (await call(b, 'get_class_info', **{'class': 'Node2D', 'member': 'position'}))['properties']
    await call(b, 'create_resource', **{'class': 'GradientTexture2D', 'assign_to': {'node': ref('Sprite'), 'property': 'texture'}})
    r = await call(b, 'get_resource', target={'node': {'scene': 'res://main.tscn', 'path': 'Sprite', 'property': 'texture'}}, properties=['width'])
    original = r['uri']
    r = await call(b, 'update_resource', target={'local': {'scene': 'res://main.tscn', 'path': 'Sprite', 'property': 'texture'}}, set={'width': 32})
    assert r['resource']['uri'] != original
    assert r['properties']['width'] == 32
    await call(b, 'edit_animation', player=ref('Anim'), name='move', create=True, length=1, tracks=[{'add': {'kind': 'value', 'path': 'Sprite:position', 'keys': [{'set': {'time': 0, 'value': vector(0, 0)}}, {'set': {'time': 1, 'value': vector(100, 0)}}]}}])
    assert len((await call(b, 'get_animation', node=ref('Anim'), animation='move'))['animations'][0]['tracks']) == 1
    pose = await call(b, 'preview_animation', player=ref('Anim'), name='move', time=.5, capture=False)
    assert pose['pose'][0]['value']['x'] == 50 and pose['restored']
    assert (await call(b, 'get_scene', path='Sprite', properties=['position']))['root']['properties']['position']['x'] == 0
    graph = await call(b, 'edit_animation_graph', tree=ref('Tree'), root_type='state_machine', states=[{'name': 'Move', 'animation': 'move'}], transitions=[{'from': 'Start', 'to': 'Move'}])
    assert graph['graph']['transitions'][0]['to'] == 'Move'
    blend = await call(b, 'edit_animation_graph', tree=ref('Tree'), root_type='blend_tree', nodes=[{'name': 'walk', 'kind': 'animation', 'animation': 'move'}, {'name': 'speed', 'kind': 'time_scale'}], connections=[{'to': 'speed', 'input': 0, 'from': 'walk'}, {'to': 'output', 'input': 0, 'from': 'speed'}], parameters={'parameters/speed/scale': 1.5})
    assert blend['parameters']['parameters/speed/scale'] == 1.5
    await call(b, 'undo_edit', edit_id=blend['edit_id'])
    await call(b, 'create_resource', **{'class': 'TileSet', 'assign_to': {'node': ref('Tiles'), 'property': 'tile_set'}})
    await call(b, 'save_documents', uris=['res://main.tscn'])
    atlas = tmp / 'atlas.svg'
    atlas.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="16"><rect width="32" height="16" fill="#138cf2"/></svg>')
    r = await call(b, 'import_assets', files=[{'source': atlas.as_uri(), 'destination': 'res://art/atlas.svg'}])
    assert r['assets'][0]['imported']
    await call(b, 'edit_tileset', target={'local': {'scene': 'res://main.tscn', 'path': 'Tiles', 'property': 'tile_set'}}, changes=[{'add_atlas': {'key': 'a', 'texture': 'res://art/atlas.svg', 'tile_size': {'x': 16, 'y': 16}}}, {'define_tile': {'source': {'key': 'a'}, 'atlas': {'x': 0, 'y': 0}}}, {'add_physics_layer': {}}, {'collision': {'source': {'key': 'a'}, 'atlas': {'x': 0, 'y': 0}, 'polygons': [[{'x': -8, 'y': -8}, {'x': 8, 'y': -8}, {'x': 8, 'y': 8}]]}}])
    r = await call(b, 'paint_tiles', layer=ref('Tiles'), region={'origin': {'x': 0, 'y': 0}, 'size': {'x': 3, 'y': 2}, 'tile': {'source_id': 0, 'atlas': {'x': 0, 'y': 0}}})
    assert r['count'] == 6
    assert len((await call(b, 'get_tilemap', layer=ref('Tiles')))['cells']) == 6
    await call(b, 'undo_edit', edit_id=r['edit_id'])
    assert not (await call(b, 'get_tilemap', layer=ref('Tiles')))['cells']
    await call(b, 'save_documents', uris=['res://main.tscn'])
    r = await call(b, 'move_assets', moves=[{'from': 'res://art/atlas.svg', 'to': 'res://art/blue.svg'}])
    assert 'res://art/blue.svg' in (b.project / 'main.tscn').read_text()
    await call(b, 'undo_edit', edit_id=r['edit_id'])
    assert (b.project / 'art/atlas.svg').exists()
    assert 'res://art/atlas.svg' in (b.project / 'main.tscn').read_text()
    await asyncio.sleep(.3)
    await call(b, 'create_scene', uri='res://base.tscn', root_class='Node2D', root_name='Base')
    await call(b, 'create_nodes', parent=ref(scene='res://base.tscn'), nodes=[{'name': 'Child', 'source': {'class': 'Node2D'}}])
    await call(b, 'save_documents', uris=['res://base.tscn'])
    await call(b, 'create_scene', uri='res://derived.tscn', inherits='res://base.tscn', root_name='Derived')
    assert (await call(b, 'get_scene', scene='res://derived.tscn', properties=['position']))['inherited_source'] == 'res://base.tscn'
    with pytest.raises(ToolError, match='inherited'):
        await call(b, 'delete_nodes', nodes=[ref('Child', 'res://derived.tscn')])
    await call(b, 'open_scene', scene='res://main.tscn')
    r = await call(b, 'apply_script_changes', patch='*** Begin Patch\n*** Add File: res://behavior.gd\n+extends Node2D\n+\n+func react(value: int) -> void:\n+\tposition.x = value\n*** End Patch', save=True, attachments=[{'script': {'uri': 'res://behavior.gd', 'node': ref('Sprite')}}])
    assert r['attachments'] == [{'script': {'uri': 'res://behavior.gd', 'node': ref('Sprite')}}]
    assert r['status'] == 'completed'
    assert 'validation' not in r['documents'][0]
    r = await call(b, 'read_scripts', documents=[{'uri': 'res://behavior.gd'}])
    revisions = r['base_revisions']
    r = await call(b, 'apply_script_changes', patch='*** Begin Patch\n*** Update File: res://behavior.gd\n@@\n-\tposition.x = value\n+\tposition.x = value * 2\n*** End Patch', base_revisions=revisions)
    assert 'validation' not in r['documents'][0]
    assert r['undo']['edit_id']
    with pytest.raises(ToolError) as caught:
        await call(b, 'apply_script_changes', patch='*** Begin Patch\n*** Update File: res://behavior.gd\n@@\n-\tposition.x = value\n+\tposition.x = value * 3\n*** End Patch', base_revisions=revisions)
    assert caught.value.code == 'REVISION_CONFLICT'
    assert (await call(b, 'read_scripts', documents=[{'uri': 'res://behavior.gd'}]))['documents'][0]['unsaved']
    await call(b, 'update_signals', connect=[{'from': ref(), 'signal': 'health_changed', 'to': ref('Sprite'), 'method': 'react'}])
    saved = await call(b, 'save_documents', uris=['res://main.tscn', 'res://behavior.gd'])
    assert saved['complete'], saved
    assert all(document['save']['state'] == 'saved' for document in saved['documents']), saved
    r = await call(b, 'delete_nodes', nodes=[ref('Sprite')])
    assert r['affected_references']
    await call(b, 'undo_edit', edit_id=r['edit_id'])
    assert (await call(b, 'find_assets', query='react', mode='symbol'))['matches']
    original = (await call(b, 'get_settings', keys=['application/config/name']))['settings']
    r = await call(b, 'update_settings', settings={'application/config/name': 'Changed'}, input_actions=[{'name': 'test_jump', 'events': [{'type': 'key', 'key': 'Space'}]}])
    await call(b, 'undo_edit', edit_id=r['edit_id'])
    assert (await call(b, 'get_settings', keys=['application/config/name']))['settings'] == original
    assert 'entries' in await call(b, 'get_logs')
    assert (await call(b, 'get_export_presets'))['presets'][0]['name'] == 'Linux Test'
    await call(b, 'save_documents', uris=['res://main.tscn'])
    exported = await call(b, 'export_build', preset='Linux Test', output=(tmp / 'test.pck').as_uri())
    assert exported['exported'] and exported['bytes'] > 0 and not exported['execution_verified']
    playback = subprocess.run([os.environ.get('GODOT', 'godot'), '--headless', '--main-pack', str(tmp / 'test.pck'), '--quit-after', '10'], capture_output=True, text=True, timeout=20)
    assert playback.returncode == 0 and 'SCRIPT ERROR' not in playback.stdout + playback.stderr, playback.stdout + playback.stderr
    log = (tmp / 'editor.log').read_text()
    assert 'SCRIPT ERROR' not in log, log


async def test_resource_target_validation_and_json_refs(editor):
    b, _tmp = editor
    await call(b, 'create_nodes', parent=ref(), nodes=[{'name': 'Sprite', 'source': {'class': 'Sprite2D'}}])
    await call(b, 'create_resource', **{'class': 'GradientTexture2D', 'assign_to': {'node': ref('Sprite'), 'property': 'texture'}})
    current = await call(b, 'get_resource', target={'node': {'scene': 'res://main.tscn', 'path': 'Sprite', 'property': 'texture'}}, properties=['width'])
    with pytest.raises(ToolError):
        await call(b, 'get_resource', target={'uri': current['uri'], 'node': {'scene': 'res://main.tscn', 'path': 'Sprite', 'property': 'texture'}})
    with pytest.raises(ToolError):
        await call(b, 'update_resource', target={'local': {'scene': 'res://main.tscn', 'path': 'Sprite', 'property': 'texture'}, 'shared': {'uri': current['uri']}}, set={'width': 32})
    unchanged = await call(b, 'get_resource', target={'node': {'scene': 'res://main.tscn', 'path': 'Sprite', 'property': 'texture'}}, properties=['width'])
    assert unchanged['properties']['width'] == current['properties']['width']
    updated = await call(b, 'update_resource', target={'local': {'scene': 'res://main.tscn', 'path': 'Sprite', 'property': 'texture'}}, set={'width': 32})
    assert updated['affected'][0] == {'node': {**ref('Sprite'), 'property': 'texture'}}


async def test_runtime_and_debugger(editor, monkeypatch):
    b, tmp = editor
    monkeypatch.delenv('GODOT_MCP_DAP_PORT', raising=False)
    d = DebugTools(b)
    run = None
    client = Client(create_server(b.project, b))
    await client.__aenter__()
    try:
        r = await call(b, 'run_scene')
        run = r['run_id']
        node = {'run_id': run, 'path': '/root/Main'}
        assert (await call(b, 'inspect_runtime', node=node, properties=['health']))['node']['properties']['health'] == 3
        result = await call(b, 'send_input', run_id=run, events=[{'event': {'action': {'action': 'ui_accept', 'pressed': True}}}, {'at_ms': 50, 'event': {'action': {'action': 'ui_accept', 'pressed': False}}}], wait_for={'property': {'node': node, 'property': 'health', 'value': 2}}, timeout_ms=2000)
        assert result['processed'] == 2 and result['condition']['satisfied']
        signal_result = await call(b, 'send_input', run_id=run, events=[{'event': {'key': {'key': 'Enter', 'pressed': True}}}, {'at_ms': 30, 'event': {'key': {'key': 'Enter', 'pressed': False}}}], wait_for={'signal': {'node': node, 'signal': 'health_changed'}}, timeout_ms=1000)
        assert signal_result['condition']['satisfied']
        mismatch = await call(b, 'wait_for_condition', run_id=run, condition={'property': {'node': node, 'property': 'health', 'value': 'wrong type'}}, timeout_ms=20)
        assert mismatch['timed_out']
        condition = await call(b, 'wait_for_condition', run_id=run, condition={'property': {'node': node, 'property': 'health', 'value': 1}}, timeout_ms=2000)
        assert condition['satisfied']
        sample = await call(b, 'sample_performance', run_id=run, duration_ms=100, metrics=['process_ms', 'objects'])
        assert sample['samples'] > 0 and sample['metrics']['objects']['mean'] > 0
        shot = await call(b, 'capture_viewport', viewport={'kind': 'game', 'run_id': run})
        pixels = base64.b64decode(shot['image_base64'])
        assert pixels.startswith(b'\x89PNG\r\n\x1a\n') and shot['width'] == 480
        (tmp / 'capture.png').write_bytes(pixels)
        await call(b, 'stop_game', run_id=run)
        await d.call('set_breakpoints', {'breakpoints': [{'uri': 'res://main.gd', 'line': 7}], 'replace': True})
        launched = await client.call_tool('run_scene', {})
        assert not launched.is_error, launched
        run = launched.structured_content['run_id']
        for _ in range(100):
            if (await b.call('_debug_state', {}))['paused']:
                break
            await asyncio.sleep(.03)
        history = await client.call_tool('get_logs', {'origin': 'runtime'})
        assert not history.is_error and history.structured_content['history']
        state = await d.call('inspect_debugger', {'run_id': run})
        assert state['frames'][0]['line'] == 7
        members = next(scope for scope in state['scopes'] if scope['name'] == 'Members')['variables']
        assert any(v['name'] == 'health' and v['value'] == '3' for v in members)
        stepped = await d.call('debug_control', {'run_id': run, 'action': 'step_into'})
        assert stepped['pause_id'] != state['pause_id']
        with pytest.raises(ToolError) as caught:
            await d.call('inspect_debugger', {'run_id': run, 'pause_id': state['pause_id'], 'frame_id': state['frame_id']})
        assert caught.value.code == 'STALE_FRAME'
        await d.call('set_breakpoints', {'breakpoints': [], 'replace': True})
        assert not (await d.call('debug_control', {'run_id': run, 'action': 'continue'}))['paused']
        await client.call_tool('stop_game', {})
        read = await client.call_tool('read_scripts', {'documents': [{'uri': 'res://main.gd'}]})
        assert not read.is_error
        patch = "*** Begin Patch\n*** Update File: res://main.gd\n@@\n func _unhandled_input(event: InputEvent) -> void:\n+\tif event.is_action_pressed(\"ui_cancel\"):\n+\t\tprint(\"MCP before crash\")\n+\t\tvar target: Variant = self\n+\t\ttarget.definitely_missing()\n*** End Patch"
        applied = await client.call_tool('apply_script_changes', {'patch': patch, 'save': True})
        assert not applied.is_error, applied
        launched = await client.call_tool('run_scene', {})
        assert not launched.is_error, launched
        run = launched.structured_content['run_id']
        failure = await client.call_tool('send_input', {'events': [{'event': {'key': {'key': 'Escape', 'pressed': True}}}], 'release_after': True})
        assert failure.is_error and failure.structured_content['error']['code'] == 'DEBUGGER_PAUSED'
        history = await client.call_tool('get_logs', {'origin': 'runtime'})
        assert not history.is_error, history
        assert any('MCP before crash' in e['message'] for e in history.structured_content['entries'])
        assert any('definitely_missing' in e['message'] for e in history.structured_content.get('exception_stops', [])), history

    finally:
        if run:
            await b.call('stop_game', {'run_id': run})
        await d.close()
        await client.__aexit__(None, None, None)
