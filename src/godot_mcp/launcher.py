"""Stable user command that starts the installation's currently active server."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    try:
        location = Path(sys.argv[0]).absolute().parent
        descriptor = json.loads((location / 'godot-mcp-launcher.json').read_text(encoding='utf-8'))
        if not isinstance(descriptor, dict) or descriptor.get('schema_version') != 1:
            raise ValueError('Unsupported launcher configuration; reinstall Godot MCP.')
        home = Path(descriptor['home'])
        if not home.is_absolute():
            raise ValueError('Launcher installation home must be absolute.')
        active = json.loads((home / 'active.json').read_text(encoding='utf-8'))
        executable = Path(active['executable'])
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError('The active executable is missing; reinstall Godot MCP.')
        if executable.resolve() == Path(sys.argv[0]).resolve():
            raise ValueError('The active executable cannot point to the launcher.')
        arguments = sys.argv[1:]
        if arguments and arguments[0] in ('connect', 'init', 'install'):
            if not any(value == '--home' or value.startswith('--home=') for value in arguments):
                arguments = [*arguments, '--home', str(home)]
        os.environ['GODOT_MCP_HOME'] = str(home)
        os.execv(str(executable), [str(executable), *arguments])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Godot MCP launcher: {exc}', file=sys.stderr)
        return 1
    return 0
