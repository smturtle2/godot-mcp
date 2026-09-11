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

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get('GODOT_MCP_INTEGRATION') != '1', reason='opt-in real editor')]


def ref(path='.', scene='res://main.tscn'):
    return {'scene': scene, 'path': path}


def vector(x, y):
    return {'$type': 'Vector2', 'x': x, 'y': y}


async def call(bridge, tool_name, **arguments):
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
    diagnostics = await call(b, 'get_diagnostics')
    assert not any('Unexpected NUL character' in entry['message'] for entry in diagnostics['entries']), diagnostics
    r = await call(b, 'create_nodes', parent=ref(), nodes=[{'name': n, 'class': c} for n, c in [('Sprite', 'Sprite2D'), ('Anim', 'AnimationPlayer'), ('Tree', 'AnimationTree'), ('Tiles', 'TileMapLayer')]])
    assert len(r['nodes']) == 4
    r = await call(b, 'update_nodes', changes=[{'node': ref('Sprite'), 'set': {'position': vector(12, 34)}}])
    assert r['nodes'][0]['properties']['position']['x'] == 12
    await call(b, 'undo_edit', edit_id=r['edit_id'])
    scene = await call(b, 'get_scene', properties=['position'])
    assert scene['root']['children'][0]['properties']['position']['x'] == 0
    assert scene['unsaved']
    assert (await call(b, 'get_class_info', **{'class': 'Node2D', 'member': 'position'}))['properties']
    await call(b, 'create_resource', **{'class': 'GradientTexture2D', 'assign_to': {'node': ref('Sprite'), 'property': 'texture'}})
    r = await call(b, 'get_resource', target={'node': ref('Sprite'), 'property': 'texture'}, properties=['width'])
    original = r['uri']
    r = await call(b, 'update_resource', target={'node': ref('Sprite'), 'property': 'texture'}, set={'width': 32}, scope='node')
    assert r['resource']['uri'] != original
    assert r['properties']['width'] == 32
    await call(b, 'edit_animation', player=ref('Anim'), name='move', create=True, length=1, tracks=[{'op': 'add', 'kind': 'value', 'path': 'Sprite:position', 'keys': [{'time': 0, 'value': vector(0, 0)}, {'time': 1, 'value': vector(100, 0)}]}])
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
    await call(b, 'edit_tileset', target={'node': ref('Tiles'), 'property': 'tile_set'}, changes=[{'op': 'add_atlas', 'key': 'a', 'texture': 'res://art/atlas.svg', 'tile_size': {'x': 16, 'y': 16}}, {'op': 'define_tile', 'source_key': 'a', 'atlas': {'x': 0, 'y': 0}}, {'op': 'add_physics_layer'}, {'op': 'collision', 'source_key': 'a', 'atlas': {'x': 0, 'y': 0}, 'polygons': [[{'x': -8, 'y': -8}, {'x': 8, 'y': -8}, {'x': 8, 'y': 8}]]}])
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
    await call(b, 'create_nodes', parent=ref(scene='res://base.tscn'), nodes=[{'name': 'Child', 'class': 'Node2D'}])
    await call(b, 'save_documents', uris=['res://base.tscn'])
    await call(b, 'create_scene', uri='res://derived.tscn', inherits='res://base.tscn', root_name='Derived')
    assert (await call(b, 'get_scene', scene='res://derived.tscn', properties=['position']))['inherited_source'] == 'res://base.tscn'
    with pytest.raises(ToolError, match='inherited'):
        await call(b, 'delete_nodes', nodes=[ref('Child', 'res://derived.tscn')])
    await call(b, 'open_scene', scene='res://main.tscn')
    r = await call(b, 'create_script', uri='res://behavior.gd', source='extends Node2D\n\nfunc react(value: int) -> void:\n\tposition.x = value\n', attach_to=[ref('Sprite')])
    assert r['attached'] == [ref('Sprite')]
    r = await call(b, 'read_script', uri='res://behavior.gd')
    revision = r['revision']
    r = await call(b, 'edit_script', uri='res://behavior.gd', if_revision=revision, edits=[{'range': {'start': {'line': 4, 'column': 15}, 'end': {'line': 4, 'column': 20}}, 'text': 'value * 2'}])
    assert r['diagnostics']['valid']
    with pytest.raises(ToolError):
        await call(b, 'edit_script', uri='res://behavior.gd', if_revision=revision, edits=[{'range': {'start': {'line': 1, 'column': 1}, 'end': {'line': 1, 'column': 1}}, 'text': '# stale\n'}])
    assert (await call(b, 'read_script', uri='res://behavior.gd'))['unsaved']
    await call(b, 'update_signals', connect=[{'from': ref(), 'signal': 'health_changed', 'to': ref('Sprite'), 'method': 'react'}])
    saved = await call(b, 'save_documents', uris=['res://main.tscn', 'res://behavior.gd'])
    assert saved['complete'], saved
    r = await call(b, 'delete_nodes', nodes=[ref('Sprite')])
    assert r['affected_references']
    await call(b, 'undo_edit', edit_id=r['edit_id'])
    assert (await call(b, 'find_assets', query='react', mode='symbol'))['matches']
    original = (await call(b, 'get_settings', keys=['application/config/name']))['settings']
    r = await call(b, 'update_settings', settings={'application/config/name': 'Changed'}, input_actions=[{'name': 'test_jump', 'events': [{'type': 'key', 'key': 'Space'}]}])
    await call(b, 'undo_edit', edit_id=r['edit_id'])
    assert (await call(b, 'get_settings', keys=['application/config/name']))['settings'] == original
    assert 'entries' in await call(b, 'get_diagnostics')
    assert (await call(b, 'get_export_presets'))['presets'][0]['name'] == 'Linux Test'
    await call(b, 'save_documents', uris=['res://main.tscn'])
    exported = await call(b, 'export_build', preset='Linux Test', output=(tmp / 'test.pck').as_uri())
    assert exported['exported'] and exported['bytes'] > 0 and not exported['execution_verified']
    playback = subprocess.run([os.environ.get('GODOT', 'godot'), '--headless', '--main-pack', str(tmp / 'test.pck'), '--quit-after', '10'], capture_output=True, text=True, timeout=20)
    assert playback.returncode == 0 and 'SCRIPT ERROR' not in playback.stdout + playback.stderr, playback.stdout + playback.stderr
    log = (tmp / 'editor.log').read_text()
    assert 'SCRIPT ERROR' not in log, log


async def test_runtime_and_debugger(editor, monkeypatch):
    b, tmp = editor
    monkeypatch.delenv('GODOT_MCP_DAP_PORT', raising=False)
    d = DebugTools(b)
    run = None
    try:
        r = await call(b, 'run_scene')
        run = r['run_id']
        node = {'run_id': run, 'path': '/root/Main'}
        assert (await call(b, 'inspect_runtime', node=node, properties=['health']))['node']['properties']['health'] == 3
        result = await call(b, 'send_input', run_id=run, events=[{'type': 'action', 'action': 'ui_accept', 'pressed': True}, {'type': 'action', 'action': 'ui_accept', 'pressed': False, 'at_ms': 50}], wait_for={'type': 'property', 'node': node, 'property': 'health', 'value': 2}, timeout_ms=2000)
        assert result['processed'] == 2 and result['condition']['satisfied']
        signal_result = await call(b, 'send_input', run_id=run, events=[{'type': 'key', 'key': 'Enter', 'pressed': True}, {'type': 'key', 'key': 'Enter', 'pressed': False, 'at_ms': 30}], wait_for={'type': 'signal', 'node': node, 'signal': 'health_changed'}, timeout_ms=1000)
        assert signal_result['condition']['satisfied']
        mismatch = await call(b, 'wait_for_condition', run_id=run, condition={'type': 'property', 'node': node, 'property': 'health', 'value': 'wrong type'}, timeout_ms=20)
        assert mismatch['timed_out']
        condition = await call(b, 'wait_for_condition', run_id=run, condition={'type': 'property', 'node': node, 'property': 'health', 'value': 1}, timeout_ms=2000)
        assert condition['satisfied']
        sample = await call(b, 'sample_performance', run_id=run, duration_ms=100, metrics=['process_ms', 'objects'])
        assert sample['samples'] > 0 and sample['metrics']['objects']['mean'] > 0
        shot = await call(b, 'capture_viewport', viewport={'kind': 'game', 'run_id': run})
        pixels = base64.b64decode(shot['image_base64'])
        assert pixels.startswith(b'\x89PNG\r\n\x1a\n') and shot['width'] == 480
        (tmp / 'capture.png').write_bytes(pixels)
        await call(b, 'stop_game', run_id=run)
        await d.call('set_breakpoints', {'breakpoints': [{'uri': 'res://main.gd', 'line': 7}], 'replace': True})
        run = (await call(b, 'run_scene'))['run_id']
        for _ in range(100):
            if (await b.call('_debug_state', {}))['paused']:
                break
            await asyncio.sleep(.03)
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
    finally:
        if run:
            await b.call('stop_game', {'run_id': run})
        await d.close()
