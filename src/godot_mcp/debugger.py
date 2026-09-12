"""Coordinate editor-owned breakpoints, DAP state, and expiring frame handles."""
from __future__ import annotations

import asyncio
import os

import psutil

from .bridge import EditorBridge, ToolError, project_path
from .dap import DAPClient
from .runtime_logs import RuntimeLogs


class DebugTools:
    def __init__(self, bridge: EditorBridge):
        self.bridge = bridge
        self.client = None
        self.connection_key = None
        self.attached_run = None
        self.pause_id = None
        self.frame_ids = set()
        self.variable_refs = set()
        self.lock = asyncio.Lock()
        self.logs = RuntimeLogs()

    async def close(self):
        if self.client:
            await self.client.close()
        self.client = None

    async def _state(self, arguments):
        state = await self.bridge.call("_debug_state", {})
        if arguments.get("run_id") != state.get("run_id") or not state.get("active"):
            raise ToolError("STALE_RUN", "This run is no longer attached to the editor debugger.")
        if self.pause_id != state.get("pause_id"):
            self.pause_id = state.get("pause_id")
            self.frame_ids.clear()
            self.variable_refs.clear()
        if "pause_id" in arguments and arguments["pause_id"] != self.pause_id:
            raise ToolError("STALE_FRAME", "The debugger resumed after this frame was observed.")
        return state

    async def _connect(self, state, *, attach=True):
        endpoint = self.bridge.endpoint()
        configured = endpoint.get("dap_port", 6006)
        if "GODOT_MCP_DAP_PORT" not in os.environ and endpoint.get("pid"):
            # Godot removes --dap-port from OS.get_cmdline_args(). Read only the
            # authenticated editor PID's actual launch arguments, never log them.
            try:
                argv = psutil.Process(int(endpoint["pid"])).cmdline()
                if "--dap-port" in argv:
                    index = argv.index("--dap-port")
                    if index + 1 < len(argv):
                        configured = argv[index + 1]
            except (psutil.Error, ValueError, TypeError):
                pass
        try:
            port = int(os.environ.get("GODOT_MCP_DAP_PORT", configured))
        except (ValueError, TypeError) as exc:
            raise ToolError("INVALID_ENDPOINT", "Invalid DAP port.") from exc
        if not 1 <= port <= 65535:
            raise ToolError("INVALID_ENDPOINT", "Invalid DAP port.")
        key = (endpoint.get("epoch"), port)
        if key != self.connection_key or self.client is None or self.client.task.done():
            await self.close()
            self.client = DAPClient(port, on_event=self.logs.receive)
            await self.client.connect(initialize=False)
            self.connection_key = key
            self.attached_run = None
        if attach and not self.client.initialized:
            retained = await self.bridge.call("_breakpoints", {"read_only": True})
            await self.client.initialize()
            for uri, lines in retained["all"].items():
                await self.client.request("setBreakpoints", {
                    "source": {"path": str(project_path(self.bridge.project, uri))},
                    "breakpoints": [{"line": line} for line in sorted(lines)], "sourceModified": False,
                })
        if attach and self.attached_run != state.get("run_id"):
            await self.client.request("attach", {"project": str(self.bridge.project)})
            self.attached_run = state.get("run_id")

    async def prepare_run(self):
        # Subscribe before launching: output and exception stops are emitted
        # by the editor even while game script execution is suspended.
        try:
            async with asyncio.timeout(2):
                await self._connect({}, attach=False)
        except (ToolError, TimeoutError) as error:
            await self.close()
            self.logs.begin(complete=False, error=str(error) or "Debug adapter connection timed out.")
        else:
            self.logs.begin()

    async def _wait_state(self, arguments, *, paused, old_pause=None):
        deadline = asyncio.get_running_loop().time() + 5
        while True:
            state = await self._state({"run_id": arguments["run_id"]})
            if state.get("paused") == paused and (not paused or state.get("pause_id") != old_pause):
                return state
            if asyncio.get_running_loop().time() >= deadline:
                raise ToolError("DEBUG_STATE_TIMEOUT", "The debugger has not reached the requested state.", state)
            await asyncio.sleep(0.03)

    async def _stack_ready(self, state):
        # Godot's stopped flag precedes the asynchronous stack-dump response.
        deadline = asyncio.get_running_loop().time() + 2
        while True:
            stack = await self.client.request("stackTrace", {"threadId": 1, "startFrame": 0, "levels": 64})
            await self._state({"run_id": state["run_id"], "pause_id": state["pause_id"]})
            if stack.get("stackFrames") or asyncio.get_running_loop().time() >= deadline:
                return stack
            await asyncio.sleep(.03)

    async def _variables_ready(self, reference, state):
        # scopes requests a remote stack dump but returns references immediately.
        # Until stack_frame_vars arrives, Godot reports its own issued IDs as unknown.
        deadline = asyncio.get_running_loop().time() + 2
        while True:
            try:
                result = await self.client.request("variables", {"variablesReference": reference})
                await self._state({"run_id": state["run_id"], "pause_id": state["pause_id"]})
                return result
            except ToolError as exc:
                if exc.code != "DAP_ERROR" or str(exc) != "unknown" or asyncio.get_running_loop().time() >= deadline:
                    raise
                await self._state({"run_id": state["run_id"], "pause_id": state["pause_id"]})
                await asyncio.sleep(.03)

    async def call(self, name: str, arguments: dict) -> dict:
        async with self.lock:
            if name == "set_breakpoints":
                current = await self.bridge.call("_breakpoints", arguments)
                state = await self.bridge.call("_debug_state", {})
                verified = []
                if state.get("active"):
                    await self._connect(state)
                    for uri, lines in current["all"].items():
                        result = await self.client.request("setBreakpoints", {
                            "source": {"path": str(project_path(self.bridge.project, uri))},
                            "breakpoints": [{"line": line} for line in sorted(lines)],
                            "sourceModified": False,
                        })
                        verified.extend({"uri": uri, **bp} for bp in result.get("breakpoints", []))
                return {"breakpoints": current["all"], "mcp_owned": current["owned"],
                        "resolved": verified, "applied_to_editor": True,
                        "applied_to_run": bool(state.get("active"))}
            state = await self._state(arguments)
            if name == "debug_control" and arguments["action"] == "step_out":
                raise ToolError("UNSUPPORTED_OPERATION", "Godot 4.7.2's GDScript DAP adapter has no stepOut request. Use step_over, step_into, or continue.")
            await self._connect(state)
            if name == "debug_control":
                action = arguments["action"]
                if action == "pause" and state["paused"]:
                    return state
                if action != "pause" and not state["paused"]:
                    raise ToolError("DEBUGGER_NOT_PAUSED", "Suspend at a breakpoint before stepping or continuing.")
                if action in ("step_over", "step_into"):
                    stack = await self._stack_ready(state)
                    if not stack.get("stackFrames"):
                        raise ToolError("NO_SCRIPT_FRAME", "The game paused outside GDScript. Continue and use a source breakpoint before stepping.")
                command = {"pause": "pause", "continue": "continue", "step_over": "next", "step_into": "stepIn"}[action]
                await self.client.request(command, {"threadId": 1})
                return await self._wait_state(arguments, paused=action != "continue", old_pause=state.get("pause_id"))
            if not state["paused"]:
                raise ToolError("DEBUGGER_NOT_PAUSED", "No suspended stack is available.")
            if ("frame_id" in arguments or "variables_reference" in arguments) and "pause_id" not in arguments:
                raise ToolError("STALE_FRAME", "Use the pause_id returned with the frame/variables handle.")
            if "variables_reference" in arguments:
                ref = arguments["variables_reference"]
                if ref not in self.variable_refs:
                    raise ToolError("STALE_FRAME", "This variables reference was not issued in the current pause.")
                result = await self._variables_ready(ref, state)
                self._remember(result.get("variables", []))
                return {"run_id": arguments["run_id"], "pause_id": self.pause_id, **result}
            stack = await self._stack_ready(state)
            frames = stack.get("stackFrames", [])
            self.frame_ids = {frame["id"] for frame in frames}
            if not frames:
                return {"run_id": arguments["run_id"], "pause_id": self.pause_id, "frames": [], "scopes": [], "reason": "No GDScript frame is available at this pause; use a source breakpoint to inspect or step."}
            frame_id = arguments.get("frame_id", frames[0]["id"])
            if frame_id not in self.frame_ids:
                raise ToolError("STALE_FRAME", "The frame does not belong to this suspended stack.")
            scopes = (await self.client.request("scopes", {"frameId": frame_id})).get("scopes", [])
            for scope in scopes:
                ref = scope.get("variablesReference", 0)
                if ref:
                    self.variable_refs.add(ref)
                    scope["variables"] = (await self._variables_ready(ref, state)).get("variables", [])
                    self._remember(scope["variables"])
            # Recheck after asynchronous DAP responses, in case the user resumed.
            await self._state({"run_id": arguments["run_id"], "pause_id": state["pause_id"]})
            return {"run_id": arguments["run_id"], "pause_id": self.pause_id,
                    "frames": frames, "frame_id": frame_id, "scopes": scopes}

    def _remember(self, variables):
        for variable in variables:
            if variable.get("variablesReference"):
                self.variable_refs.add(variable["variablesReference"])
