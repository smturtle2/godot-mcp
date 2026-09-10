#!/usr/bin/env python3
"""Run a bounded clean-project installation and editor smoke check."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def run(command: list[str], *, cwd: Path, env: dict, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=True)


def installed_executable(home: Path) -> Path:
    candidates = sorted([*home.glob("versions/*/environment/bin/godot-mcp"),
                         *home.glob("versions/*/environment/Scripts/godot-mcp.exe")])
    if not candidates:
        raise RuntimeError(f"No installed executable under {home}")
    return candidates[-1]


async def mcp_smoke(executable: Path, project: Path, env: dict[str, str], home: Path, *, edit: bool = True) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=str(executable), args=["connect", "--home", str(home)], env=env, cwd=project.parent)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            listed = await client.list_tools()
            context_result = await client.call_tool("get_context", {})
            context = context_result.structured_content or {}
            if not edit:
                assert not context_result.is_error
                assert context.get("server_ready") is True
                assert context.get("projects", []) == []
                installed = await client.call_tool("install_plugin", {"project": str(project)})
                assert not installed.is_error, installed
                assert (project / "addons/godot_mcp/plugin.cfg").is_file()
                return {"tools": len(listed.tools), "context": context, "plugin_installed_by_mcp": True}
            created = await client.call_tool("create_nodes", {
                "parent": {"scene": "res://main.tscn", "path": "."},
                "nodes": [{"name": "SmokeChild", "class": "Node2D", "properties": {
                    "position": {"$type": "Vector2", "x": 12, "y": 34}
                }}]
            })
            scene = await client.call_tool("get_scene", {"scene": "res://main.tscn", "path": ".", "depth": 1})
            assert len(listed.tools) == 43 and len({tool.name for tool in listed.tools}) == 43
            assert not context_result.is_error and context.get("version")
            assert context["version"].startswith("v") and context["protocol"]
            assert Path(context["project"]).resolve() == project.resolve()
            assert context["engine"]["major"] >= 4
            assert not created.is_error and not scene.is_error
            children = scene.structured_content["root"]["children"]
            child = next(item for item in children if item["name"] == "SmokeChild")
            assert child["properties"]["position"]["x"] == 12
            assert child["properties"]["position"]["y"] == 34
            return {"tools": len(listed.tools), "context": context, "child": child["name"],
                    "position": child["properties"]["position"]}


def verify(source: Path, godot: str, work_dir: Path | None) -> dict:
    source = source.resolve()
    owned = work_dir is None
    if owned:
        temp = tempfile.TemporaryDirectory(prefix="godot-mcp-verify-")
        root = Path(temp.name)
    else:
        root = Path(tempfile.mkdtemp(prefix="godot-mcp-verify-", dir=work_dir))
    try:
        project = root / "project"
        shutil.copytree(source / "tests/fixtures", project)
        home = root / "install"
        installer_env = dict(os.environ, PYTHONPATH=str(source / "src"))
        clean_env = dict(os.environ)
        clean_env.pop("PYTHONPATH", None)
        installer = [sys.executable, "-m", "godot_mcp.cli", "install", "--source", str(source),
                     "--home", str(home), "--no-modify-path"]
        first = run(installer, cwd=source, env=installer_env, timeout=90)
        executable = installed_executable(home)
        active = json.loads((home / "active.json").read_text())
        if Path(active["executable"]).resolve() != executable.resolve() or not executable.is_file():
            raise RuntimeError("Active installation does not point to the installed executable")
        stable = home / "bin" / ("godot-mcp.exe" if os.name == "nt" else "godot-mcp")
        stable_bytes = stable.read_bytes()
        command_env = dict(clean_env, PATH=str(stable.parent) + os.pathsep + clean_env.get("PATH", ""))
        assert run(["godot-mcp", "version"], cwd=project, env=command_env).returncode == 0
        version = run([str(executable), "version"], cwd=project, env=clean_env)
        global_smoke = asyncio.run(mcp_smoke(stable, project, clean_env, home, edit=False))
        link = ["godot-mcp", "init"]
        run(link, cwd=project, env=command_env, timeout=30)
        check_before = subprocess.run([str(executable), "check", "--project", str(project)], cwd=project, env=clean_env,
                                      capture_output=True, text=True, timeout=10)
        with socket.socket() as dap_socket, socket.socket() as debug_socket:
            dap_socket.bind(("127.0.0.1", 0))
            debug_socket.bind(("127.0.0.1", 0))
            dap_port = dap_socket.getsockname()[1]
            debug_port = debug_socket.getsockname()[1]
        editor_log = (root / "godot-editor.log").open("w")
        editor = subprocess.Popen([godot, "--headless", "--editor", "--path", str(project), "--dap-port", str(dap_port),
                                    "--debug-server", f"tcp://127.0.0.1:{debug_port}"],
                                  cwd=project, env=clean_env, start_new_session=True, stdout=editor_log,
                                  stderr=subprocess.STDOUT, text=True)
        endpoint = project / ".godot-mcp/endpoint.json"
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not endpoint.exists():
                if editor.poll() is not None:
                    raise RuntimeError("Godot editor exited before creating endpoint")
                time.sleep(0.25)
            if not endpoint.exists():
                raise RuntimeError("Timed out waiting for Godot MCP endpoint")
            assert check_before.returncode != 0
            smoke = asyncio.run(mcp_smoke(stable, project, clean_env, home))
            check_after = run([str(executable), "check", "--project", str(project)], cwd=project, env=clean_env, timeout=15)
        finally:
            editor.terminate()
            try:
                editor.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(editor.pid, 9)
                editor.wait(timeout=5)
            editor_log.close()
        previous_endpoint = json.loads(endpoint.read_text())
        previous_endpoint.update({'pid': editor.pid, 'version': 'v0.0.0_0'})
        endpoint.write_text(json.dumps(previous_endpoint, indent=2), encoding='utf-8')
        second = run(installer, cwd=source, env=installer_env, timeout=90)
        second_executable = installed_executable(home)
        assert second_executable == executable
        stale_endpoint_update_passed = True
        repair = run(installer + ["--repair"], cwd=source, env=installer_env, timeout=90)
        repaired_executable = installed_executable(home)
        assert stable.read_bytes() == stable_bytes
        assert run(["godot-mcp", "version"], cwd=project, env=command_env).returncode == 0
        init_after_repair = run(["godot-mcp", "init"], cwd=project, env=command_env)
        assert json.loads(init_after_repair.stdout)["executable"] == str(repaired_executable)
        transactions = list((home / "transactions").iterdir())
        if repaired_executable == second_executable:
            raise RuntimeError("Repair did not create a new executable environment")
        if not transactions:
            raise RuntimeError("Repair did not retain an installation transaction backup")
        return {"ok": True, "project": str(project), "install_home": str(home), "executable": str(executable),
                "second_executable": str(second_executable), "reused_on_reinstall": executable == second_executable,
                "stable_command": str(stable), "stable_command_repair_passed": True,
                "repaired_executable": str(repaired_executable), "repair_created_new": repaired_executable != second_executable,
                "stale_endpoint_update_passed": stale_endpoint_update_passed,
                "transaction_count": len(transactions),
                "version": version.stdout.strip(), "global_smoke": global_smoke,
                "check_before_editor_exit": check_before.returncode,
                "check_after_editor": check_after.stdout.strip(), "smoke": smoke,
                "installer_output": first.stdout[-1000:] + second.stdout[-1000:] + repair.stdout[-1000:]}
    finally:
        if owned:
            temp.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--godot", default=shutil.which("godot") or shutil.which("godot4") or "godot")
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(verify(args.source, args.godot, args.work_dir), indent=2))
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
