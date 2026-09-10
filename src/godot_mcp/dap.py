"""Minimal asynchronous DAP client for the Godot editor's documented adapter."""
from __future__ import annotations

import asyncio
import contextlib
import json
from collections import deque

from .bridge import ToolError


class DAPClient:
    def __init__(self, port: int, timeout: float = 10):
        self.port = port
        self.timeout = timeout
        self.reader = None
        self.writer = None
        self.task = None
        self.sequence = 0
        self.pending = {}
        self.events = deque(maxlen=500)

    async def connect(self):
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", self.port), self.timeout
            )
        except (OSError, TimeoutError) as exc:
            raise ToolError("DAP_DISCONNECTED", "Enable the Godot Debug Adapter server in Editor Settings > Network.") from exc
        self.task = asyncio.create_task(self._read())
        return await self.request("initialize", {
            "clientID": "godot-mcp", "adapterID": "godot", "pathFormat": "path",
            "linesStartAt1": True, "columnsStartAt1": True,
            "supportsVariableType": True, "supportsVariablePaging": False,
            "supportsRunInTerminalRequest": False,
        })

    async def _read(self):
        failure = ToolError("DAP_DISCONNECTED", "The Godot debug adapter closed the connection.")
        try:
            while True:
                headers = await self.reader.readuntil(b"\r\n\r\n")
                fields = dict(line.split(b":", 1) for line in headers.split(b"\r\n") if b":" in line)
                length = int(fields.get(b"Content-Length", b"0"))
                if not 0 < length <= 8 * 1024 * 1024:
                    raise ValueError("DAP payload size is invalid")
                message = json.loads(await self.reader.readexactly(length))
                if message.get("type") == "response":
                    future = self.pending.pop(message.get("request_seq"), None)
                    if future and not future.done():
                        if message.get("success", False):
                            future.set_result(message.get("body", {}))
                        else:
                            future.set_exception(ToolError("DAP_ERROR", message.get("message", "Debug adapter rejected the request."), message.get("body", {})))
                elif message.get("type") == "event":
                    self.events.append(message)
        except asyncio.CancelledError:
            pass
        except (OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ValueError, TypeError) as exc:
            failure = ToolError("DAP_DISCONNECTED", f"Debug adapter communication ended: {exc}")
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(failure)
            self.pending.clear()

    async def request(self, command: str, arguments: dict | None = None) -> dict:
        if not self.writer or self.writer.is_closing():
            raise ToolError("DAP_DISCONNECTED", "Debug adapter is not connected.")
        self.sequence += 1
        seq = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[seq] = future
        payload = json.dumps({"seq": seq, "type": "request", "command": command,
                              "arguments": arguments or {}}, ensure_ascii=False).encode()
        try:
            self.writer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload)
            await self.writer.drain()
            return await asyncio.wait_for(future, self.timeout)
        except TimeoutError as exc:
            raise ToolError("DAP_TIMEOUT", f"Godot did not answer {command} before the deadline.") from exc
        except OSError as exc:
            raise ToolError("DAP_DISCONNECTED", str(exc)) from exc
        finally:
            self.pending.pop(seq, None)

    async def close(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        if self.writer:
            self.writer.close()
            with contextlib.suppress(OSError):
                await self.writer.wait_closed()
        self.writer = None
