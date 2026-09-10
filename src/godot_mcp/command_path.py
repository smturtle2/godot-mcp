"""Register a user-owned command directory without touching MCP client settings."""
from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path


def register_path(directory: Path) -> str:
    directory = directory.resolve()
    if any(Path(item).expanduser().resolve() == directory for item in os.environ.get('PATH', '').split(os.pathsep) if item):
        return 'Command directory is already on PATH.'
    if sys.platform == 'win32':
        return _windows_path(directory)
    shell = Path(os.environ.get('SHELL', '/bin/sh')).name
    if shell == 'zsh':
        profile = Path(os.environ.get('ZDOTDIR', str(Path.home()))) / '.zshrc'
        line = f'export PATH={shlex.quote(str(directory))}:"$PATH"'
    elif shell == 'fish':
        profile = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'fish/conf.d/godot-mcp.fish'
        quoted = str(directory).replace('\\', '\\\\').replace("'", "\\'")
        line = f"fish_add_path --prepend '{quoted}'"
    else:
        profile = Path.home() / ('.bashrc' if shell == 'bash' else '.profile')
        line = f'export PATH={shlex.quote(str(directory))}:"$PATH"'
    existing = profile.read_text(encoding='utf-8') if profile.exists() else ''
    if line not in existing.splitlines():
        profile.parent.mkdir(parents=True, exist_ok=True)
        with profile.open('a', encoding='utf-8') as handle:
            handle.write(f'\n# Godot MCP user command\n{line}\n')
    return f'PATH configured in {profile}. Open a new terminal to use godot-mcp.'


def _windows_path(directory: Path) -> str:
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            prior, value_type = winreg.QueryValueEx(key, 'Path')
        except FileNotFoundError:
            prior, value_type = '', winreg.REG_EXPAND_SZ
        entries = [part for part in prior.split(';') if part]
        normalized = {os.path.normcase(os.path.expandvars(part).rstrip('\\/')) for part in entries}
        if os.path.normcase(str(directory).rstrip('\\/')) not in normalized:
            winreg.SetValueEx(key, 'Path', 0, value_type, ';'.join([str(directory), *entries]))
    # Notify desktop applications; already-running terminals keep their environment.
    import ctypes
    from ctypes import wintypes
    result = ctypes.c_size_t()
    broadcast = ctypes.windll.user32.SendMessageTimeoutW
    broadcast.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    broadcast.restype = wintypes.LPARAM
    broadcast(0xFFFF, 0x001A, 0, 'Environment', 0x0002, 1000, ctypes.byref(result))
    return 'User PATH configured. Open a new terminal to use godot-mcp.'
