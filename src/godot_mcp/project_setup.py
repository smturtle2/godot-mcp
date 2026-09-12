"""New-project preparation and editor connection, reusing the plugin installer."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import psutil

from .bridge import EditorBridge, ToolError
from .installer import _atomic_write, initialize_project


class ProjectSetup:
    def __init__(self, home: Path):
        self.home = home.resolve()
        self.lock = asyncio.Lock()

    async def create(self, project: Path, name: str | None = None, editor: str | None = None) -> dict:
        async with self.lock:
            return await self._create(project.resolve(), name, editor)

    async def _create(self, project: Path, name: str | None, editor: str | None) -> dict:
        key = hashlib.sha256(str(project).encode()).hexdigest()
        journal = self.home / "project-starts" / f"{key}.json"
        try:
            record = json.loads(journal.read_text()) if journal.exists() else {}
        except (OSError, ValueError) as error:
            raise ToolError("SETUP_RECORD_INVALID", "Cannot read the retained project setup record.") from error
        if not isinstance(record, dict) or record and (record.get("project") != str(project) or
                any(type(record.get(key)) is not bool for key in ("project_created", "plugin_installed"))):
            raise ToolError("SETUP_RECORD_INVALID", "The retained project setup record is invalid.")
        if not record:
            if project.exists() and (not project.is_dir() or any(project.iterdir())):
                raise ToolError("PROJECT_NOT_EMPTY", "Choose a new or empty directory; use install_plugin for an existing project.")
            record = {"project": str(project), "project_created": False, "plugin_installed": False}
        result = {"project": str(project), "status": "partial", "project_created": record["project_created"],
                  "plugin_installed": record["plugin_installed"], "editor_started": False, "connected": False}
        stage = "create"
        try:
            if not record["project_created"]:
                project.mkdir(parents=True, exist_ok=True)
                # Exclusive creation also protects against another creator winning the race.
                with (project / "project.godot").open("x", encoding="utf-8") as stream:
                    stream.write('config_version=5\n\n[application]\n\nconfig/name=' + json.dumps(name or project.name) + '\n')
                record["project_created"] = result["project_created"] = True
                _atomic_write(journal, json.dumps(record))
            elif not (project / "project.godot").is_file():
                raise ToolError("PROJECT_MISSING", "The previously created project.godot is missing; reconcile the project before retrying.")

            stage = "connect"
            bridge = EditorBridge(project, timeout=1)
            try:
                context = await bridge.call("get_context", {})
            except ToolError as error:
                if error.code not in {"EDITOR_DISCONNECTED", "VERSION_MISMATCH"}:
                    raise
            else:
                result.update(status="completed", plugin_installed=True, editor_started=True, connected=True, context=context)
                return result

            running = False
            if record.get("pid"):
                try:
                    process = psutil.Process(record["pid"])
                    running = process.is_running() and process.create_time() == record.get("process_created_at")
                except psutil.NoSuchProcess:
                    pass
            if not running:
                stage = "install"
                # The installer owns its rollback and active-editor guards.
                if not record["plugin_installed"]:
                    installed = await asyncio.to_thread(initialize_project, project, self.home)
                    record["plugin_installed"] = result["plugin_installed"] = True
                    result["installation_backup"] = installed["backup"]
                    _atomic_write(journal, json.dumps(record))
                stage = "launch"
                executable = editor or os.environ.get("GODOT") or shutil.which("godot") or shutil.which("godot4")
                if not executable:
                    raise ToolError("EDITOR_NOT_FOUND", "Pass editor or set GODOT to a Godot executable, then retry create_project.")
                log_path = project / ".godot-mcp" / "editor.log"
                result["editor_log"] = str(log_path)
                with log_path.open("ab") as log:
                    process = await asyncio.create_subprocess_exec(
                        executable, "--editor", "--path", str(project), stdin=subprocess.DEVNULL,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=os.name == "posix",
                        env={**os.environ, "GODOT_MCP_HOME": str(self.home)},
                    )
                result.update(editor_started=True, editor_pid=process.pid)
                record.update(pid=process.pid, process_created_at=psutil.Process(process.pid).create_time())
                _atomic_write(journal, json.dumps(record))
            result.update(editor_started=True, editor_pid=record["pid"])
            stage = "connect"
            deadline = time.monotonic() + 15
            while True:
                try:
                    context = await bridge.call("get_context", {})
                except ToolError as error:
                    if error.code != "EDITOR_DISCONNECTED":
                        raise
                    if not psutil.pid_exists(record["pid"]):
                        raise ToolError("EDITOR_EXITED", "Godot exited before connecting. Inspect editor_log, then retry create_project.") from error
                    if time.monotonic() >= deadline:
                        raise ToolError("EDITOR_CONNECT_PENDING", "Godot started but has not connected yet. Retry create_project to reconnect without launching another editor.") from error
                    await asyncio.sleep(.2)
                else:
                    result.update(status="completed", connected=True, context=context)
                    return result
        except (OSError, ValueError, psutil.Error, ToolError) as error:
            result["failures"] = [{"phase": stage, "code": error.code if isinstance(error, ToolError) else "PROJECT_SETUP_FAILED", "message": str(error)}]
            result["editor_log"] = str(project / ".godot-mcp" / "editor.log")
            return result
