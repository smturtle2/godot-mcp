from __future__ import annotations

import asyncio
import os
import shutil
import signal
import socket
import subprocess
from pathlib import Path

import pytest

from godot_mcp.bridge import EditorBridge, ToolError


@pytest.fixture
async def editor(tmp_path, request):
    project = tmp_path / 'project'
    shutil.copytree(Path(__file__).parent / 'fixtures', project)
    shutil.copytree(Path(__file__).parents[1] / 'src/godot_mcp/addon', project / 'addons/godot_mcp')
    prepare = getattr(request, 'param', None)
    if prepare is not None:
        prepare(project)
    log = (tmp_path / 'editor.log').open('w')
    with socket.socket() as dap, socket.socket() as debug:
        dap.bind(('127.0.0.1', 0))
        debug.bind(('127.0.0.1', 0))
        dap_port, debug_port = dap.getsockname()[1], debug.getsockname()[1]
    process = subprocess.Popen([os.environ.get('GODOT', 'godot'), '--headless', '--editor', '--path', str(project), '--dap-port', str(dap_port), '--debug-server', f'tcp://127.0.0.1:{debug_port}'], stdout=log, stderr=subprocess.STDOUT, start_new_session=os.name == 'posix')
    bridge = EditorBridge(project, timeout=60)
    try:
        for _ in range(300):
            if process.poll() is not None:
                pytest.fail((tmp_path / 'editor.log').read_text())
            try:
                context = await bridge.call('get_context', {})
                if context['active_scene']:
                    break
            except ToolError:
                pass
            await asyncio.sleep(.1)
        else:
            pytest.fail((tmp_path / 'editor.log').read_text())
        yield bridge, tmp_path
    finally:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
