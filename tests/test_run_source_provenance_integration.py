"""Observe real game behavior separately from startup file provenance."""
from __future__ import annotations

import json
import os

import pytest
from mcp import Client
from test_source_workflow_integration import finished, invoke

from godot_mcp.server import create_server

pytestmark = [pytest.mark.integration, pytest.mark.skipif(os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real editor")]


async def test_run_revision_guard_startup_observation_and_changed_source(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        _, read = await invoke(client, "read_scripts", documents=[{"uri": "res://main.gd"}])
        response, stale = await invoke(client, "run_scene", revisions={"res://main.gd": "0" * 64})
        assert response.is_error and stale["error"]["code"] == "REVISION_CONFLICT"
        response, run = await invoke(client, "run_scene", revisions=read["base_revisions"])
        assert not response.is_error, run
        proof = run["source_provenance"]
        assert proof["startup_files"] == "matched" and proof["state"] == "matches_startup", json.dumps(proof)
        assert proof["behavior"] == "unverified" and not proof["restart_required"]
        run_id = run["run_id"]
        _, observed = await invoke(client, "wait_for_condition", run_id=run_id, condition={"scene": {"uri": "res://main.tscn"}})
        assert observed["satisfied"]
        assert observed["source_provenance"]["source_snapshot_id"] == proof["source_snapshot_id"]

        patch = "*** Begin Patch\n*** Update File: res://main.gd\n@@\n-var health: int = 3\n+var health: int = 5\n*** End Patch"
        _, receipt = await invoke(client, "apply_script_changes", patch=patch, base_revisions=read["base_revisions"], wait_ms=0)
        changed = await finished(client, receipt)
        assert changed["status"] == "completed", changed
        assert changed["runtime"]["state"] == "source_changed" and changed["runtime"]["restart_required"], changed
        response, blocked = await invoke(client, "run_scene", restart=True)
        assert response.is_error and blocked["error"]["code"] == "UNSAVED_DOCUMENTS"
        _, context = await invoke(client, "get_context", scope="runtime")
        assert context["run_id"] == run_id and context["running"]
        _, read = await invoke(client, "read_scripts", documents=[{"uri": "res://main.gd"}])
        response, restarted = await invoke(client, "run_scene", restart=True, save_uris=["res://main.gd"], revisions=read["base_revisions"])
        assert not response.is_error and restarted["run_id"] != run_id, restarted
        assert restarted["source_provenance"]["state"] == "matches_startup", restarted
        assert restarted["source_provenance"]["source_snapshot_id"] != proof["source_snapshot_id"]
        _, observed = await invoke(client, "wait_for_condition", run_id=restarted["run_id"], condition={"property": {"node": {"run_id": restarted["run_id"], "path": "/root/Main"}, "property": "health", "value": 5}})
        assert observed["satisfied"], observed
        _, observed = await invoke(client, "send_input", run_id=restarted["run_id"], events=[{"event": {"action": {"action": "ui_accept", "pressed": True}}}, {"at_ms": 50, "event": {"action": {"action": "ui_accept", "pressed": False}}}], wait_for={"property": {"node": {"run_id": restarted["run_id"], "path": "/root/Main"}, "property": "health", "value": 4}})
        assert observed["complete"], observed
        await invoke(client, "stop_game", run_id=restarted["run_id"])


async def test_current_diagnostics_are_pending_then_fresh_and_cache_dependencies(editor):
    bridge, _ = editor
    async with Client(create_server(bridge.project, bridge)) as client:
        response, pending = await invoke(client, "get_diagnostics", uris=["res://main.gd"], wait_ms=0)
        assert not response.is_error and pending["state"] == "pending" and "error_count" not in pending
        _, context = await invoke(client, "get_context")
        assert any(op["operation_id"] == pending["operation_id"] for op in context["pending_operations"])
        first = await finished(client, pending)
        assert first["state"] == "valid" and first["error_count"] == 0 and first["cache"] == "compiled", first
        _, repeated = await invoke(client, "get_diagnostics", uris=["res://main.gd"], wait_ms=0)
        reused = await finished(client, repeated)
        assert reused["cache"] == "reused" and reused["fingerprint"] == first["fingerprint"], reused
        await invoke(client, "update_settings", settings={"application/config/name": "Changed current settings"})
        _, request = await invoke(client, "get_diagnostics", uris=["res://main.gd"], wait_ms=0)
        changed = await finished(client, request)
        assert changed["cache"] == "compiled" and changed["fingerprint"] != first["fingerprint"], changed
        response, unsaved = await invoke(client, "run_scene")
        assert response.is_error and unsaved["error"]["code"] == "UNSAVED_DOCUMENTS" and "res://project.godot" in unsaved["error"]["details"]["uris"], unsaved
