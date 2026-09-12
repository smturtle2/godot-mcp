"""Build the small environment used when launching the Godot editor.

Only display-session variables are discovered.  In particular, this helper
does not attempt to infer display names and never changes ``os.environ``.
Process environments can be unreadable on Linux, so discovery is best effort;
failure to find a graphical session is left for Godot to report.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shlex
from collections.abc import Mapping
from pathlib import Path

import psutil

_ALLOWED_KEYS = frozenset(
    {
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XDG_RUNTIME_DIR",
        "XAUTHORITY",
        "DBUS_SESSION_BUS_ADDRESS",
    }
)
_GRAPHICS_KEYS = frozenset({"DISPLAY", "WAYLAND_DISPLAY"})


def _validated_overrides(overrides: Mapping[str, str] | None) -> dict[str, str]:
    if overrides is None:
        return {}
    if not isinstance(overrides, Mapping):
        raise ValueError("overrides must be a mapping of environment strings")
    result: dict[str, str] = {}
    for key, value in overrides.items():
        if (
            not isinstance(key, str)
            or key not in _ALLOWED_KEYS
            or not isinstance(value, str)
            or "\x00" in value
        ):
            raise ValueError("overrides may contain only whitelisted string keys and values")
        result[key] = value
    return result


def _has_graphics(environment: Mapping[str, str]) -> bool:
    return any(environment.get(key) for key in _GRAPHICS_KEYS)


def _copy_whitelist(environment: Mapping[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in environment.items()
        if key in _ALLOWED_KEYS and isinstance(value, str)
    }


def _ancestor_session_environment() -> dict[str, str] | None:
    """Return the first readable same-UID ancestor with a display variable."""
    try:
        uid = os.getuid()
        process = psutil.Process(os.getpid())
        while True:
            try:
                process = process.parent()
            except (OSError, psutil.Error):
                return None
            if process is None:
                return None
            try:
                if process.uids().real != uid:
                    continue
                environment = process.environ()
            except (OSError, ValueError, psutil.Error):
                continue
            if _has_graphics(environment):
                return _copy_whitelist(environment)
    except (OSError, ValueError, psutil.Error):
        return None


def _runtime_directory(uid: int) -> str | None:
    candidate = Path(f"/run/user/{uid}")
    try:
        stat = candidate.stat()
    except OSError:
        return None
    if candidate.is_dir() and stat.st_uid == uid:
        return str(candidate)
    return None


async def _systemd_user_environment(base: Mapping[str, str]) -> dict[str, str] | None:
    child_environment = dict(base)
    runtime_directory = _runtime_directory(os.getuid())
    if runtime_directory is not None:
        child_environment["XDG_RUNTIME_DIR"] = runtime_directory
    try:
        process = await asyncio.create_subprocess_exec(
            "systemctl",
            "--user",
            "show-environment",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=child_environment,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=2.0)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            finally:
                await process.wait()
            return None
    except (asyncio.TimeoutError, OSError, ValueError):
        return None
    if not stdout:
        return None
    try:
        text = stdout.decode()
    except UnicodeDecodeError:
        return None
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        try:
            fields = shlex.split(line, comments=False)
        except ValueError:
            continue
        if len(fields) != 1 or "=" not in fields[0]:
            continue
        key, value = fields[0].split("=", 1)
        if key in _ALLOWED_KEYS and "\x00" not in value:
            parsed[key] = value
    return parsed if _has_graphics(parsed) else None


async def editor_environment(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return an inherited environment augmented with a graphical session.

    Explicit display overrides, and an already inherited display, are
    authoritative.  On Linux, readable same-UID ancestors are checked first,
    then the user's systemd manager.  Missing GUI information is not an error.
    """
    environment = dict(os.environ)
    validated = _validated_overrides(overrides)

    # A caller-supplied display key is intentional even when its value is an
    # empty string (which can be used to explicitly clear an inherited value).
    explicit_graphics = bool(_GRAPHICS_KEYS.intersection(validated))
    if platform.system() != "Linux" or explicit_graphics or _has_graphics(environment):
        environment.update(validated)
        return environment

    discovered = _ancestor_session_environment()
    if discovered is None:
        discovered = await _systemd_user_environment(environment)
    if discovered is not None:
        for key in _ALLOWED_KEYS:
            environment.pop(key, None)
        environment.update(discovered)
    environment.update(validated)
    return environment
