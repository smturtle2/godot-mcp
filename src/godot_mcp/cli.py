"""Command-line entry point for the Godot MCP server."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from .server import create_server, serve
from .version import ENGINE_VERSION, PRODUCT_VERSION, PROTOCOL_VERSION


def project_arg(value: str) -> Path:
    project = Path(value).expanduser().resolve()
    if not (project / "project.godot").is_file():
        raise argparse.ArgumentTypeError(f"project.godot not found in {project}")
    return project


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="godot-mcp")
    p.add_argument("--version", action="version", version=f"%(prog)s {PRODUCT_VERSION} (engine {ENGINE_VERSION}, protocol {PROTOCOL_VERSION})")
    sub = p.add_subparsers(dest="command")
    serve_parser = sub.add_parser("serve", help="serve MCP over stdio")
    serve_parser.add_argument("--project", required=True, type=project_arg)
    check_parser = sub.add_parser("check", help="check catalog and editor connection")
    check_parser.add_argument("--project", required=True, type=project_arg)
    sub.add_parser("version", help="print version information")
    from .installer import default_home
    init_parser = sub.add_parser("init", help="install and enable the plugin in a Godot project")
    init_parser.add_argument("project", nargs="?", type=project_arg, default=Path.cwd())
    init_parser.add_argument("--home", type=Path, default=default_home())
    connect_parser = sub.add_parser("connect", help="serve MCP over stdio with project discovery")
    connect_parser.add_argument("--home", type=Path, default=default_home())
    install_parser = sub.add_parser("install", help="install or update the server")
    install_parser.add_argument("installer_args", nargs=argparse.REMAINDER)
    return p


def _version() -> int:
    print(f"product={PRODUCT_VERSION} engine={ENGINE_VERSION} protocol={PROTOCOL_VERSION}")
    return 0


async def _check(project: Path) -> int:
    from .bridge import EditorBridge, ToolError

    try:
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            server = create_server(project, EditorBridge(project))
            server_task = asyncio.create_task(server.run(*server_streams, server.create_initialization_options()))
            try:
                async with ClientSession(*client_streams) as client:
                    await client.initialize()
                    listed = await client.list_tools()
                    if len(listed.tools) != 43 or len({tool.name for tool in listed.tools}) != 43:
                        print("Catalog check failed: MCP list_tools did not return 43 unique tools.", file=sys.stderr)
                        return 1
                    result = await client.call_tool("get_context", {})
                    if result.is_error:
                        error = result.structured_content.get("error", {}) if isinstance(result.structured_content, dict) else {}
                        code = error.get("code", "EDITOR_ERROR")
                        kind = "Installation" if code in {"EDITOR_DISCONNECTED", "INVALID_ENDPOINT", "PROJECT_MISMATCH", "VERSION_MISMATCH"} else "Connection"
                        print(f"{kind} check failed: {code}: {error.get('message', 'Editor error')}", file=sys.stderr)
                        return 1
                    context = result.structured_content
            finally:
                server_task.cancel()
                await asyncio.gather(server_task, return_exceptions=True)
    except ToolError as exc:
        endpoint_errors = {"EDITOR_DISCONNECTED", "INVALID_ENDPOINT", "PROJECT_MISMATCH", "VERSION_MISMATCH"}
        kind = "Installation" if exc.code in endpoint_errors else "Connection"
        print(f"{kind} check failed: {exc.code}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(context, dict):
        print("Connection check failed: get_context returned a non-object result.", file=sys.stderr)
        return 1
    engine = context.get("engine", {})
    actual_engine = ".".join(str(engine.get(key, "")) for key in ("major", "minor", "patch")) if isinstance(engine, dict) else ""
    if (not context.get("project") or Path(str(context["project"])).resolve() != project.resolve()
            or context.get("version") != PRODUCT_VERSION
            or actual_engine != ENGINE_VERSION
            or context.get("protocol") != PROTOCOL_VERSION):
        print("Connection check failed: get_context version/project metadata does not match.", file=sys.stderr)
        return 1
    print("MCP catalog: 43 tools")
    print("Editor connection: OK (get_context)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "install":
        try:
            from . import installer
        except ImportError as exc:
            print(f"Installer unavailable: {exc}", file=sys.stderr)
            return 1
        return int(installer.main(args[1:]))
    # A project-only invocation is a convenient alias for serve.
    if args and args[0] == "--project":
        args.insert(0, "serve")
    ns = parser().parse_args(args)
    if ns.command == "init":
        from .installer import initialize_project
        try:
            print(json.dumps(initialize_project(ns.project, ns.home), indent=2))
        except (OSError, ValueError) as exc:
            print(f"Plugin installation failed: {exc}", file=sys.stderr)
            return 1
        return 0
    if ns.command == "connect":
        asyncio.run(serve(None, home=ns.home))
        return 0
    if ns.command == "version":
        return _version()
    if ns.command == "serve":
        asyncio.run(serve(ns.project))
        return 0
    if ns.command == "check":
        return asyncio.run(_check(ns.project))
    if ns.command == "install":
        try:
            from . import installer
        except ImportError as exc:
            print(f"Installer unavailable: {exc}", file=sys.stderr)
            return 1
        return int(installer.main(ns.installer_args))
    parser().error("a command is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
