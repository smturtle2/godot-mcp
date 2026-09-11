"""Authenticated, bounded loopback calls; timed-out mutations are never retried."""
from __future__ import annotations

import asyncio
import json
import math
import uuid
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from .version import PRODUCT_VERSION


class ToolError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def result(self) -> dict:
        return {"error": {"code": self.code, "message": str(self), "details": self.details}}


def project_path(project: Path, uri: str, *, root_allowed: bool = False) -> Path:
    if not isinstance(uri, str) or not uri.startswith("res://"):
        raise ToolError("INVALID_PATH", "Expected a res:// project URI.")
    relative = uri[6:]
    if "\\" in relative or "\x00" in relative or ".." in relative.split("/"):
        raise ToolError("INVALID_PATH", "Project URI contains traversal or invalid separators.")
    path = (project / relative).resolve()
    if not path.is_relative_to(project.resolve()) or (path == project.resolve() and not root_allowed):
        raise ToolError("INVALID_PATH", "Path must name a file inside the project.")
    return path


def validate_values(project: Path, value, depth: int = 0) -> None:
    if depth > 40:
        raise ToolError("INVALID_ARGUMENT", "Input nesting exceeds 40 levels.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ToolError("INVALID_ARGUMENT", "Numbers must be finite.")
    if isinstance(value, str):
        if "\x00" in value:
            raise ToolError("INVALID_ARGUMENT", "NUL characters are not accepted.")
        if value.startswith("res://"):
            project_path(project, value, root_allowed=True)
    elif isinstance(value, list):
        for item in value:
            validate_values(project, item, depth + 1)
    elif isinstance(value, dict):
        tag = value.get("$type")
        if tag:
            fields = {
                "Vector2": "xy", "Vector2i": "xy", "Vector3": "xyz", "Vector3i": "xyz",
                "Vector4": "xyzw", "Vector4i": "xyzw", "Quaternion": "xyzw", "Color": "rgba",
            }
            if tag in fields:
                for field in fields[tag]:
                    if field not in value or isinstance(value[field], bool) or not isinstance(value[field], (int, float)):
                        raise ToolError("INVALID_VALUE", f"{tag}.{field} must be numeric.")
                if tag.endswith("i") and any(int(value[f]) != value[f] for f in fields[tag]):
                    raise ToolError("INVALID_VALUE", f"{tag} components must be integers.")
                if tag == "Color" and value.get("space", "linear") not in ("linear", "srgb"):
                    raise ToolError("INVALID_VALUE", "Color space must be linear or srgb.")
            elif tag in ("NodePath", "StringName"):
                if not isinstance(value.get("value"), str):
                    raise ToolError("INVALID_VALUE", f"{tag} requires string value.")
            elif tag == "Resource":
                uri = value.get("uri", "")
                if not isinstance(uri, str) or not uri.startswith(("res://", "godot://resources/")):
                    raise ToolError("INVALID_VALUE", "Resource requires a resource URI.")
            elif tag in ("Rect2", "Rect2i"):
                if not all(isinstance(value.get(f), dict) and "x" in value[f] and "y" in value[f] for f in ("position", "size")):
                    raise ToolError("INVALID_VALUE", f"{tag} requires position and size vectors.")
            elif tag in ("Transform2D", "Basis", "Transform3D"):
                expected = {"Transform2D": ("x", "y", "origin"), "Basis": ("x", "y", "z"), "Transform3D": ("basis", "origin")}[tag]
                if not all(isinstance(value.get(f), dict) for f in expected):
                    raise ToolError("INVALID_VALUE", f"{tag} requires {', '.join(expected)} objects.")
            elif tag in ("PackedByteArray", "PackedInt32Array", "PackedInt64Array", "PackedFloat32Array", "PackedFloat64Array", "PackedStringArray", "PackedVector2Array", "PackedVector3Array", "PackedVector4Array", "PackedColorArray"):
                if not isinstance(value.get("values"), list):
                    raise ToolError("INVALID_VALUE", f"{tag} requires a values array.")
            else:
                raise ToolError("INVALID_VALUE", f"Unsupported Godot value tag: {tag}")
        for child in value.values():
            validate_values(project, child, depth + 1)


class EditorBridge:
    def __init__(self, project: Path, timeout: float = 30):
        self.project = project.resolve()
        self.timeout = timeout
        self.lock = asyncio.Lock()

    def endpoint(self) -> dict:
        try:
            value = json.loads((self.project / ".godot-mcp/endpoint.json").read_text())
        except (OSError, ValueError) as exc:
            raise ToolError("EDITOR_DISCONNECTED", "Open this project in Godot and enable the Godot MCP plugin.") from exc
        if not isinstance(value, dict):
            raise ToolError("INVALID_ENDPOINT", "Malformed editor endpoint.")
        if Path(value.get("project", "")).resolve() != self.project:
            raise ToolError("PROJECT_MISMATCH", "The endpoint belongs to a different project.")
        if type(value.get("port")) is not int or not 1 <= value["port"] <= 65535:
            raise ToolError("INVALID_ENDPOINT", "The endpoint has an invalid port.")
        if not isinstance(value.get("token"), str) or len(value["token"]) < 32:
            raise ToolError("INVALID_ENDPOINT", "The endpoint has an invalid token.")
        if value.get("version") != PRODUCT_VERSION:
            raise ToolError("VERSION_MISMATCH", "Update the project's plugin to match the installed server.",
                            {"server": PRODUCT_VERSION, "plugin": value.get("version")})
        return value

    async def call(self, name: str, arguments: dict) -> dict:
        validate_values(self.project, arguments)
        config = self.endpoint()
        call_id = uuid.uuid4().hex
        # Input duration and condition waiting are sequential, not concurrent.
        event_ms = max((e.get("at_ms", 0) for e in arguments.get("events", [])), default=0)
        seconds = self.timeout
        if name == "get_diagnostics":
            seconds = max(seconds, 90)
        if event_ms or "timeout_ms" in arguments:
            seconds = max(seconds, (arguments.get("timeout_ms", 0) + event_ms) / 1000 + 10)
        if "duration_ms" in arguments:
            seconds = max(seconds, arguments["duration_ms"] / 1000 + 10)
        async with self.lock:
            try:
                async with asyncio.timeout(min(195, seconds)):
                    async with connect(f"ws://127.0.0.1:{config['port']}", proxy=None,
                                       open_timeout=5, close_timeout=1, max_size=32 * 1024 * 1024) as ws:
                        await ws.send(json.dumps({"id": call_id, "token": config["token"],
                                                  "method": name, "params": arguments}, allow_nan=False))
                        response = json.loads(await ws.recv())
                if not isinstance(response, dict) or response.get("id") != call_id:
                    raise ToolError("INVALID_RESPONSE", "The editor returned an invalid response ID.")
                if "error" in response:
                    error = response["error"]
                    raise ToolError(error.get("code", "EDITOR_ERROR"), error.get("message", "Editor error"),
                                    error.get("details"))
                if not isinstance(response.get("result"), dict):
                    raise ToolError("INVALID_RESPONSE", "The editor returned a non-object result.")
                return response["result"]
            except TimeoutError as exc:
                raise ToolError("TIMEOUT", "The editor call timed out; its outcome is unknown. Inspect state before retrying a mutation.",
                                {"outcome": "unknown", "request_id": call_id, "tool": name, "automatically_retried": False}) from exc
            except (OSError, WebSocketException, ValueError, KeyError, TypeError) as exc:
                raise ToolError("EDITOR_DISCONNECTED", f"Editor communication failed; its outcome is unknown: {exc}",
                                {"outcome": "unknown", "request_id": call_id, "tool": name, "automatically_retried": False}) from exc
