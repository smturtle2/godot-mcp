"""Register the Godot MCP server in supported client configuration files."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path


def _command(executable: Path, project: Path) -> tuple[str, list[str]]:
    return str(executable.resolve()), ["serve", "--project", str(project.resolve())]


def _same_project(value: object, project: str) -> bool:
    args = value.get("args") if isinstance(value, dict) else None
    return isinstance(args, Sequence) and not isinstance(args, (str, bytes)) and len(args) >= 3 and args[-1] == project


def _key(servers: dict, name: str, project: str) -> str:
    if name not in servers or _same_project(servers[name], project):
        return name
    suffix = hashlib.sha256(project.encode()).hexdigest()[:8]
    candidate = f"{name}-{suffix}"
    counter = 2
    while candidate in servers and not _same_project(servers[candidate], project):
        candidate = f"{name}-{suffix}-{counter}"
        counter += 1
    return candidate


def _backup(path: Path) -> Path:
    stamp = time.time_ns()
    target = path.with_name(f"{path.name}.bak.{stamp}")
    while target.exists():
        stamp += 1
        target = path.with_name(f"{path.name}.bak.{stamp}")
    target.write_bytes(path.read_bytes())
    target.chmod(path.stat().st_mode & 0o7777)
    return target


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o7777 if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _json_config(path: Path, name: str, executable: Path, project: Path, vscode: bool) -> tuple[str, str]:
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON configuration; no changes made: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON configuration must be an object; no changes made: {path}")
    root_name = "servers" if vscode else "mcpServers"
    servers = data.setdefault(root_name, {})
    if not isinstance(servers, dict):
        raise ValueError(f"{root_name} must be an object; no changes made: {path}")
    project_text = str(project.resolve())
    key = _key(servers, name, project_text)
    command, args = _command(executable, project)
    entry = dict(servers.get(key, {})) if isinstance(servers.get(key), dict) else {}
    if vscode:
        entry["type"] = "stdio"
    entry.update({"command": command, "args": args})
    changed = servers.get(key) != entry
    servers[key] = entry
    output = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return key, output if changed else path.read_text()


def _toml_config(path: Path, name: str, executable: Path, project: Path) -> tuple[str, str]:
    from tomlkit import dumps, parse, table

    source = path.read_text() if path.exists() else ""
    try:
        document = parse(source)
    except Exception as exc:
        raise ValueError(f"Invalid TOML configuration; no changes made: {path}") from exc
    servers = document.get("mcp_servers")
    if servers is None:
        servers = table()
        document["mcp_servers"] = servers
    if not hasattr(servers, "get"):
        raise ValueError("mcp_servers must be a table; no changes made")
    project_text = str(project.resolve())
    existing = dict(servers)
    key = _key(existing, name, project_text)
    command, args = _command(executable, project)
    entry = servers.get(key)
    if entry is None:
        entry = table()
        servers[key] = entry
    if not hasattr(entry, "__setitem__"):
        raise ValueError(f"mcp_servers.{key} must be a table; no changes made")
    entry["command"] = command
    entry["args"] = ["serve", "--project", project_text]
    return key, dumps(document)


def register_client(path: Path, name: str, executable: Path, project: Path, format: str = "json") -> dict:
    """Register a version-isolated server and return paths/settings metadata."""
    path, executable, project = Path(path), Path(executable), Path(project)
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name):
        raise ValueError("name must be a non-empty safe server name")
    if format not in {"json", "vscode", "codex"}:
        raise ValueError("format must be json, vscode, or codex")
    if format == "codex":
        key, output = _toml_config(path, name, executable, project)
    else:
        key, output = _json_config(path, name, executable, project, format == "vscode")
    changed = not path.exists() or output != path.read_text()
    backup = _backup(path) if changed and path.exists() else None
    if changed:
        _atomic_write(path, output)
    return {"server_key": key, "backup_path": str(backup) if backup else None,
            "config_path": str(path.resolve()), "settings": {"command": str(executable.resolve()),
            "args": ["serve", "--project", str(project.resolve())]}}


def register_global_client(path: Path, name: str, executable: Path, home: Path, format: str = "json") -> dict:
    """Register the user-wide stdio server without binding it to a project."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name):
        raise ValueError("name must be a non-empty safe server name")
    path, executable, home = Path(path), Path(executable), Path(home)
    command, args = str(executable.resolve()), ["connect", "--home", str(home.resolve())]
    if format not in {"json", "vscode", "codex"}:
        raise ValueError("format must be json, vscode, or codex")
    if format == "codex":
        from tomlkit import dumps, parse, table
        source = path.read_text() if path.exists() else ""
        try:
            doc = parse(source)
        except Exception as exc:
            raise ValueError(f"Invalid TOML configuration; no changes made: {path}") from exc
        servers = doc.setdefault("mcp_servers", table())
        existing = dict(servers)
        def identity(value):
            return isinstance(value, dict) and list(value.get("args", [])) == args
        def migratable(value):
            return (isinstance(value, dict) and Path(str(value.get("command", ""))).name.startswith("godot-mcp")
                    and list(value.get("args", []))[:1] == ["serve"])
        key = name if name in servers and (identity(servers[name]) or migratable(servers[name])) else _key(existing, name, str(home.resolve()))
        entry = servers.get(key, table())
        entry["command"], entry["args"] = command, args
        servers[key] = entry
        output = dumps(doc)
    else:
        try:
            data = json.loads(path.read_text()) if path.exists() else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid JSON configuration; no changes made: {path}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"JSON configuration must be an object; no changes made: {path}")
        root = "servers" if format == "vscode" else "mcpServers"
        servers = data.setdefault(root, {})
        if not isinstance(servers, dict):
            raise ValueError(f"{root} must be an object; no changes made: {path}")
        def identity(value):
            return isinstance(value, dict) and value.get("args") == args
        def migratable(value):
            return (isinstance(value, dict) and Path(str(value.get("command", ""))).name.startswith("godot-mcp")
                    and list(value.get("args", []))[:1] == ["serve"])
        key = name if name in servers and (identity(servers[name]) or migratable(servers[name])) else _key(servers, name, str(home.resolve()))
        entry = dict(servers.get(key, {})) if isinstance(servers.get(key), dict) else {}
        if format == "vscode":
            entry["type"] = "stdio"
        entry.update(command=command, args=args)
        servers[key] = entry
        output = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    changed = not path.exists() or output != path.read_text()
    backup = _backup(path) if changed and path.exists() else None
    if changed:
        _atomic_write(path, output)
    return {"server_key": key, "backup_path": str(backup) if backup else None,
            "config_path": str(path.resolve()), "settings": {"command": command, "args": args}}
