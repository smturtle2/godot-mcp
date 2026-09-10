"""Official MCP SDK server; the editor remains the source of project state."""
from __future__ import annotations

import asyncio
import copy
import json
from contextlib import asynccontextmanager
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .bridge import EditorBridge, ToolError, validate_values
from .catalog import SPECS, TOOL_SPECS
from .version import PRODUCT_VERSION


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
            error = next(validators[params.name].iter_errors(arguments), None)
            if error:
                raise ToolError("INVALID_ARGUMENT", error.message, {"path": list(error.absolute_path)})
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
                return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result))], structured_content=result)
            selector = arguments.pop("project", None)
            if directory and params.name == "get_context" and not selector and not selected_project and len(directory.projects()) != 1:
                result = directory.context()
                return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result))], structured_content=result)
            active_bridge = fixed_bridge or directory.select(selector or selected_project)
            active_project = active_bridge.project
            if fixed_bridge and selector and Path(selector).resolve() != active_project:
                raise ToolError("PROJECT_MISMATCH", "This dedicated server is bound to a different project.")
            validate_values(active_project, arguments)
            if params.name in ("inspect_debugger", "set_breakpoints", "debug_control"):
                if active_project not in debuggers:
                    from .debugger import DebugTools
                    debuggers[active_project] = DebugTools(active_bridge)
                result = await debuggers[active_project].call(params.name, arguments)
            else:
                result = await active_bridge.call(params.name, arguments)
            if directory:
                selected_project = str(active_project)
            result = copy.deepcopy(result)
            result.setdefault("project", str(active_project))
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
            return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False)), *images], structured_content=result)
        except ToolError as exc:
            result = exc.result()
            return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result))],
                                        structured_content=result, is_error=True)

    return Server("Godot MCP", version=PRODUCT_VERSION, on_list_tools=list_tools,
                  on_call_tool=call_tool, lifespan=lifespan,
                  instructions="For a project without the plugin, call install_plugin with its absolute path while Godot is closed, then ask the user to open it. Call get_context first for editor work. When several projects are open, select an absolute project path. Use live scene/resource references for editor edits and current run_id for gameplay. Save explicitly before play. After timeout inspect state before retrying a mutation. Tool errors describe recoverable conditions.")


async def serve(project: Path | None = None, *, home: Path | None = None) -> None:
    server = create_server(project, home=home)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
