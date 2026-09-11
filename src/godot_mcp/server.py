"""Official MCP SDK server; the editor remains the source of project state."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .bridge import EditorBridge, ToolError, validate_values
from .catalog import SPECS, TOOL_SPECS
from .input_validation import validate_arguments
from .result_projection import project_result
from .source_tools import SourceTools
from .version import PRODUCT_VERSION

SERVER_INSTRUCTIONS = (
    "For editor work, call get_context first; select an absolute project. Prefer MCP for live edits. "
    "Use live refs and current run_id. Read sources with read_scripts, then apply_script_changes with its base_revisions. "
    "Save explicitly before play. For pending work, query get_operation_result; never replay a mutation to wait. "
    "After a timeout without an operation ID, inspect state before retrying. For direct edits, check unsaved state, then reload and validate. "
    "Godot values use $type and named fields. Pass these rules to delegates."
)


def _tool_result(name: str, result: dict, *, project: str | None = None) -> types.CallToolResult:
    result = project_result(name, result)
    if project is not None:
        result.setdefault("project", project)
    images = []

    def extract(value):
        if isinstance(value, dict):
            data = value.pop("image_base64", None)
            if data:
                images.append(types.ImageContent(type="image", mime_type="image/png", data=data))
            for child in value.values():
                extract(child)
        elif isinstance(value, list):
            for child in value:
                extract(child)

    extract(result)
    incomplete = ("error" in result or result.get("status") in {"partial", "failed"}
                  or (result.get("complete") is False and result.get("status") != "pending"))
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, separators=(",", ":"))), *images],
        structured_content=result, is_error=incomplete,
    )


def create_server(project: Path | None = None, bridge: EditorBridge | None = None, *, home: Path | None = None) -> Server:
    from .installer import default_home, initialize_project
    install_home = home or default_home()
    fixed_bridge = bridge or (EditorBridge(project) if project else None)
    directory = None
    if fixed_bridge is None:
        from .discovery import EditorDirectory
        directory = EditorDirectory(install_home)
    validators = {name: Draft202012Validator(spec["inputSchema"]) for name, spec in SPECS.items()}
    debuggers = {}
    selected_project: str | None = None

    @asynccontextmanager
    async def lifespan(server):
        yield {}
        for debugger in debuggers.values():
            await debugger.close()

    async def list_tools(ctx, params):
        return types.ListToolsResult(tools=[types.Tool(**spec) for spec in TOOL_SPECS])

    async def call_tool(ctx, params):
        nonlocal selected_project
        try:
            if params.name not in SPECS:
                raise ToolError("UNKNOWN_TOOL", f"Unknown tool: {params.name}")
            arguments = dict(params.arguments or {})
            validate_arguments(validators[params.name], arguments)
            if params.name == "install_plugin":
                target = Path(arguments["project"])
                if not target.is_absolute():
                    raise ToolError("INVALID_ARGUMENT", "project must be an absolute path.")
                if fixed_bridge and target.resolve() != fixed_bridge.project:
                    raise ToolError("PROJECT_MISMATCH", "This dedicated server is bound to a different project.")
                try:
                    result = await asyncio.to_thread(initialize_project, target, install_home)
                except (OSError, ValueError) as exc:
                    raise ToolError("INSTALL_FAILED", str(exc)) from exc
                return _tool_result(params.name, result)
            selector = arguments.pop("project", None)
            if directory and params.name == "get_context" and not selector and not selected_project and len(directory.projects()) != 1:
                result = directory.context()
                return _tool_result(params.name, result)
            active_bridge = fixed_bridge or directory.select(selector or selected_project)
            active_project = active_bridge.project
            if fixed_bridge and selector and Path(selector).resolve() != active_project:
                raise ToolError("PROJECT_MISMATCH", "This dedicated server is bound to a different project.")
            validate_values(active_project, arguments)
            if params.name in {"apply_script_changes", "resume_script_changes", "get_diagnostics", "get_operation_result"}:
                result = await SourceTools(active_bridge).call(params.name, arguments)
            elif params.name in ("inspect_debugger", "set_breakpoints", "debug_control"):
                if active_project not in debuggers:
                    from .debugger import DebugTools
                    debuggers[active_project] = DebugTools(active_bridge)
                result = await debuggers[active_project].call(params.name, arguments)
            else:
                result = await active_bridge.call(params.name, arguments)
            if directory:
                selected_project = str(active_project)
            return _tool_result(params.name, result, project=str(active_project))
        except ToolError as exc:
            result = exc.result()
            return _tool_result(params.name, result)

    return Server("Godot MCP", version=PRODUCT_VERSION, on_list_tools=list_tools,
                  on_call_tool=call_tool, lifespan=lifespan,
                  instructions=SERVER_INSTRUCTIONS)


async def serve(project: Path | None = None, *, home: Path | None = None) -> None:
    server = create_server(project, home=home)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
