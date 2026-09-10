"""Small terminal presentation helpers; redirected output stays plain text."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _paint(text: str, color: str, stream=None) -> str:
    stream = stream or sys.stdout
    if stream.isatty() and 'NO_COLOR' not in os.environ and os.environ.get('TERM') != 'dumb':
        return f'\033[{color}m{text}\033[0m'
    return text


def heading(title: str) -> None:
    print('\n' + _paint(title, '1;36'))
    print(_paint('=' * min(len(title), 60), '36'), flush=True)


def step(number: int, text: str) -> None:
    print(f"  {_paint(f'[{number}/3]', '36')} {text}", flush=True)


def success(command: Path, path_status: str, project: Path | None) -> None:
    print('\n  ' + _paint('READY', '1;32'))
    if path_status:
        print(f'  {path_status}')
    print('\n  ' + _paint('MCP client command', '1'))
    print(f'    "{command}" connect')
    print('  Your MCP client starts and stops the server.')
    if project:
        print('\n  ' + _paint('Project linked', '1'))
        print(f'    {project}')
        print('  Open it in Godot, then ask your AI to check the connection.')
    else:
        print('\n  ' + _paint('Set up a project', '1'))
        print('    godot-mcp init')
        print('  Run in a Godot project folder, or ask your AI to install the plugin.')
    print()


def failure(message: str) -> None:
    print('\n' + _paint('INSTALLATION FAILED', '1;31', sys.stderr), file=sys.stderr)
    print(message, file=sys.stderr)
