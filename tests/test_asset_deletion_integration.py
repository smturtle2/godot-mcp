"""Focused real-editor deletion/recovery lifecycle and truthful partial effects."""
from __future__ import annotations

import os

import pytest

from godot_mcp.bridge import ToolError
from godot_mcp.source_tools import SourceTools

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get('GODOT_MCP_INTEGRATION') != '1', reason='opt-in real editor')]


def prepare_assets(project):
    folder = project / 'delete_pack'
    folder.mkdir()
    (folder / 'helper.gd').write_text('extends Node\n')
    (folder / 'tex.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8" fill="#138cf2"/></svg>')
    (project / 'keep.tscn').write_text('[gd_scene load_steps=2 format=3]\n\n[ext_resource type="Script" path="res://delete_pack/helper.gd" id="1"]\n\n[node name="Keep" type="Node"]\nscript = ExtResource("1")\n')


async def finish(bridge, receipt):
    if receipt['status'] != 'pending':
        return receipt
    return (await SourceTools(bridge).operation(receipt['operation_id'], 60000))['result']


async def preview(bridge, **options):
    return await bridge.call('delete_assets', {'action': {'preview': options}})


async def apply(bridge, plan):
    return await finish(bridge, await bridge.call('delete_assets', {'action': {'apply': {'plan_id': plan['plan_id']}}}))


@pytest.mark.parametrize('editor', [prepare_assets], indirect=True)
async def test_asset_recovery_and_permanent_lifecycle(editor):
    bridge, _ = editor
    folder = bridge.project / 'delete_pack'
    blocked = await preview(bridge, paths=['res://delete_pack'])
    assert not blocked['can_apply'] and any(r['owner'] == 'res://keep.tscn' for r in blocked['references'])
    options = {'paths': ['res://delete_pack'], 'references': 'allow_broken'}
    stale = await preview(bridge, **options)
    (folder / 'helper.gd').write_text('extends Node\nvar changed = true\n')
    with pytest.raises(ToolError) as conflict:
        await apply(bridge, stale)
    assert conflict.value.code == 'STALE_PLAN'
    originals = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    plan = await preview(bridge, **options)
    assert plan['can_apply'], plan
    removed = await apply(bridge, plan)
    assert removed['complete'] and removed['editor_sync'] == 'completed', removed
    assert removed['remaining_references'] and not folder.exists()
    assert any(p.endswith('.uid') for p in removed['applied'])
    assert any(p.endswith('.import') for p in removed['applied'])
    assert (await bridge.call('get_context', {}))['recoverable_deletions'][0]['deletion_id'] == removed['deletion_id']
    # A colliding external file is never replaced by Undo or explicit restoration.
    folder.mkdir()
    (folder / 'helper.gd').write_text('external file\n')
    with pytest.raises(ToolError) as conflict:
        await bridge.call('restore_assets', {'deletion_id': removed['deletion_id']})
    assert conflict.value.code == 'RESTORE_CONFLICT'
    (folder / 'helper.gd').unlink()
    restored = await finish(bridge, await bridge.call('undo_edit', {'edit_id': removed['edit_id']}))
    assert restored['complete'], restored
    for name, content in originals.items():
        assert (folder / name).read_bytes() == content
    removed = await apply(bridge, await preview(bridge, **options))
    purge = await bridge.call('purge_deleted_assets', {'action': {'preview': {'deletion_ids': [removed['deletion_id']]}}})
    purged = await bridge.call('purge_deleted_assets', {'action': {'apply': {'plan_id': purge['plan_id']}}})
    assert purged['complete'] and purged['applied'] == [removed['deletion_id']], purged
    with pytest.raises(ToolError) as conflict:
        await bridge.call('undo_edit', {'edit_id': removed['edit_id']})
    assert conflict.value.code == 'EDIT_CONFLICT'
    # Never-saved source has the same explicit deletion and recovery lifecycle.
    sources = SourceTools(bridge)
    draft = await sources.call('apply_script_changes', {'patch': '*** Begin Patch\n*** Add File: res://draft.gd\n+extends Node\n*** End Patch', 'wait_ms': 0})
    await sources.operation(draft['operation_id'], 60000)
    blocked = await preview(bridge, paths=['res://draft.gd'])
    assert not blocked['can_apply']
    plan = await preview(bridge, paths=['res://draft.gd'], include_unsaved=['res://draft.gd'])
    removed = await apply(bridge, plan)
    assert removed['complete'], removed
    restored = await finish(bridge, await bridge.call('restore_assets', {'deletion_id': removed['deletion_id']}))
    assert restored['complete'] and not (bridge.project / 'draft.gd').exists(), restored
    current = await bridge.call('read_scripts', {'documents': [{'uri': 'res://draft.gd'}]})
    assert current['documents'][0]['source'] == 'extends Node\n'
    await bridge.call('save_documents', {'uris': ['res://draft.gd']})
    plan = await preview(bridge, paths=['res://draft.gd'], mode='permanent')
    permanent = await apply(bridge, plan)
    assert permanent['complete'] and permanent['edit_id'] is None and not permanent['recovery']['recoverable'], permanent
    with pytest.raises(ToolError) as conflict:
        await bridge.call('restore_assets', {'deletion_id': permanent['deletion_id']})
    assert conflict.value.code == 'PERMANENT_DELETION'


def prepare_partial(project):
    (project / 'a.txt').write_text('removed\n')
    (project / 'b.txt').write_text('retained\n')
    script = project / 'addons/godot_mcp/asset_deletions.gd'
    script.write_text(script.read_text().replace(
        'else: error = DirAccess.rename_absolute(uri, backup)',
        'elif uri == "res://b.txt": error = ERR_FILE_CANT_WRITE\n\t\t\t\telse: error = DirAccess.rename_absolute(uri, backup)'))


@pytest.mark.parametrize('editor', [prepare_partial], indirect=True)
async def test_partial_deletion_reports_actual_files_and_restores(editor):
    bridge, _ = editor
    removed = await apply(bridge, await preview(bridge, paths=['res://a.txt', 'res://b.txt'], references='allow_broken'))
    assert removed['status'] == 'partial' and removed['applied'] == ['res://a.txt'], removed
    assert removed['remaining'] == ['res://b.txt'] and removed['failures'][0]['code'] == 'DELETE_FAILED'
    assert not (bridge.project / 'a.txt').exists() and (bridge.project / 'b.txt').read_text() == 'retained\n'
    restored = await finish(bridge, await bridge.call('restore_assets', {'deletion_id': removed['deletion_id']}))
    assert restored['complete'] and (bridge.project / 'a.txt').read_text() == 'removed\n', restored
