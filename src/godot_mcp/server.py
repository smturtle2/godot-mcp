"""Official MCP SDK server; the editor remains the source of project state."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from jsonschema import Draft202012Validator
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .bridge import EditorBridge, ToolError, validate_values
from .catalog import SPECS, TOOL_SPECS
from .client_state import ClientState
from .guide import read_guide
from .input_validation import validate_arguments
from .result_projection import project_result, result_summary
from .source_tools import SourceTools
from .version import PRODUCT_VERSION

SERVER_INSTRUCTIONS = (
    "Godot MCP provides tools for developing games in the live Godot editor.\n"
    "Use get_guide to learn this server's capabilities, usage, and Godot\n"
    "development practices. Read the sections relevant to your task."
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
        content=[types.TextContent(type="text", text=result_summary(name, result)), *images],
        structured_content=result, is_error=incomplete,
    )


def create_server(project: Path | None = None, bridge: EditorBridge | None = None, *, home: Path | None = None) -> Server:
    from .installer import default_home, initialize_project
    from .project_setup import ProjectSetup
    install_home = home or default_home()
    project_setup = ProjectSetup(install_home)
    fixed_bridge = bridge or (EditorBridge(project) if project else None)
    directory = None
    if fixed_bridge is None:
        from .discovery import EditorDirectory
        directory = EditorDirectory(install_home)
    validators = {name: Draft202012Validator(spec["inputSchema"]) for name, spec in SPECS.items()}
    debuggers = {}

    @asynccontextmanager
    async def lifespan(server):
        yield {"client_state": ClientState()}
        for debugger in debuggers.values():
            await debugger.close()

    async def list_tools(ctx, params):
        return types.ListToolsResult(tools=[types.Tool(**spec) for spec in TOOL_SPECS])

    async def call_tool(ctx, params):
        client_state = ctx.lifespan_context["client_state"]
        try:
            if params.name not in SPECS:
                raise ToolError("UNKNOWN_TOOL", f"Unknown tool: {params.name}")
            arguments = dict(params.arguments or {})
            validate_arguments(validators[params.name], arguments)
            if params.name == "get_guide":
                return types.CallToolResult(content=[types.TextContent(
                    type="text", text=read_guide(arguments.get("section"), arguments.get("tool")),
                )], is_error=False)
            if params.name in {"install_plugin", "create_project"}:
                target = Path(arguments["project"])
                if not target.is_absolute():
                    raise ToolError("INVALID_ARGUMENT", "project must be an absolute path.")
                if fixed_bridge and target.resolve() != fixed_bridge.project:
                    raise ToolError("PROJECT_MISMATCH", "This dedicated server is bound to a different project.")
                if params.name == "create_project":
                    validate_values(target, arguments)
                    result = await project_setup.create(target, arguments.get("name"), arguments.get("editor"), arguments.get("environment"))
                    if result.get("connected") and directory:
                        client_state.selected_project = str(target.resolve())
                    return _tool_result(params.name, result)
                try:
                    result = await asyncio.to_thread(initialize_project, target, install_home)
                except (OSError, ValueError) as exc:
                    raise ToolError("INSTALL_FAILED", str(exc)) from exc
                return _tool_result(params.name, result)
            selector = arguments.pop("project", None)
            if directory and params.name == "get_context" and not selector and not client_state.selected_project and len(directory.projects()) != 1:
                result = directory.context()
                return _tool_result(params.name, result)
            active_bridge = fixed_bridge or directory.select(selector or client_state.selected_project)
            active_project = active_bridge.project
            if fixed_bridge and selector and Path(selector).resolve() != active_project:
                raise ToolError("PROJECT_MISMATCH", "This dedicated server is bound to a different project.")
            validate_values(active_project, arguments)
            arguments = client_state.prepare(str(active_project), params.name, arguments)
            if params.name in {"apply_script_changes", "resume_script_changes", "get_diagnostics", "get_operation_result"}:
                result = await SourceTools(active_bridge).call(params.name, arguments)
            elif params.name in ("inspect_debugger", "set_breakpoints", "debug_control"):
                if active_project not in debuggers:
                    from .debugger import DebugTools
                    debuggers[active_project] = DebugTools(active_bridge)
                result = await debuggers[active_project].call(params.name, arguments)
            elif params.name == "run_scene":
                if active_project not in debuggers:
                    from .debugger import DebugTools
                    debuggers[active_project] = DebugTools(active_bridge)
                debugger = debuggers[active_project]
                previous = debugger.logs.current
                await debugger.prepare_run()
                try:
                    result = await active_bridge.call(params.name, arguments)
                except ToolError as error:
                    if error.details.get("run_id"):
                        debugger.logs.bind(error.details["run_id"])
                    else:
                        debugger.logs.current = previous
                    raise
                debugger.logs.bind(result["run_id"])
                try:
                    result["debugger"] = await active_bridge.call("_debug_state", {})
                except ToolError as error:
                    result["runtime_observation_error"] = error.result()["error"]
                history = debugger.logs.read({"run_id": result["run_id"], "kinds": ["error"], "limit": 10})
                result["startup_errors"] = history["entries"]
                if history["entries"]:
                    result["status"] = "partial"
                    result["failures"] = [{"phase": "startup", "code": "RUNTIME_ERROR", "message": entry["message"]}
                                          for entry in history["entries"]]
                if history.get("collection_error"):
                    result["log_collection_error"] = history["collection_error"]
            elif params.name == "get_logs" and arguments.get("run_id") and active_project in debuggers and arguments["run_id"] in debuggers[active_project].logs.runs:
                retained = debuggers[active_project].logs.read({**arguments, "since": 0, "kinds": ["error"], "limit": 2000})
                try:
                    result = await active_bridge.call(params.name, arguments)
                except ToolError as error:
                    if error.code not in {"STALE_RUN", "EDITOR_DISCONNECTED"}:
                        raise
                    result = debuggers[active_project].logs.read(arguments)
                stops = [entry for entry in retained["entries"] if entry.get("event") == "stopped"]
                if stops:
                    result["exception_stops"] = stops[-1:]
            else:
                result = await active_bridge.call(params.name, arguments)
            client_state.observe(str(active_project), params.name, result)
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
