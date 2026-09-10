#!/usr/bin/env python3
"""Compatibility entry point for source checkouts and the original HTTPS URL."""
from __future__ import annotations

import runpy
import tempfile
import urllib.request
from pathlib import Path

source = Path(__file__).resolve().parents[1] / 'src/godot_mcp/bootstrap.py'
if source.is_file():
    runpy.run_path(str(source), run_name='__main__')
else:
    url = 'https://raw.githubusercontent.com/smturtle2/godot-mcp/main/src/godot_mcp/bootstrap.py'
    with urllib.request.urlopen(url, timeout=30) as response:
        if not response.url.startswith('https://'):
            raise ValueError('Bootstrap requires HTTPS.')
        data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ValueError('Bootstrap exceeds size limit.')
    with tempfile.TemporaryDirectory(prefix='godot-mcp-bootstrap-') as directory:
        entry = Path(directory) / 'bootstrap.py'
        entry.write_bytes(data)
        runpy.run_path(str(entry), run_name='__main__')
