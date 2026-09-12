"""Source patch preparation and bounded waiting over the editor-owned workflow."""
from __future__ import annotations

import asyncio
import time

from .bridge import EditorBridge, ToolError
from .source_patch import build_plan, parse_patch


class SourceTools:
    def __init__(self, bridge: EditorBridge):
        self.bridge = bridge

    async def operation(self, operation_id: str, wait_ms: int = 0) -> dict:
        deadline = time.monotonic() + wait_ms / 1000
        while True:
            value = await self.bridge.call("get_operation_result", {"operation_id": operation_id})
            if not value.get("pending") or time.monotonic() >= deadline:
                return value
            await asyncio.sleep(min(.1, max(0, deadline - time.monotonic())))

    async def call(self, name: str, arguments: dict) -> dict:
        if name == "get_operation_result":
            return await self.operation(arguments["operation_id"], arguments.get("wait_ms", 0))
        wait_ms = arguments.get("wait_ms", 1500 if name == "get_diagnostics" else 15000)
        if name in {"resume_script_changes", "get_diagnostics"}:
            result = await self.bridge.call(name, {key: value for key, value in arguments.items() if key != "wait_ms"})
        else:
            files = parse_patch(arguments["patch"])
            bases = arguments.get("base_revisions", {})
            updates = {item.uri for item in files if not item.create}
            if set(bases) != updates:
                raise ToolError("BASE_REVISIONS_REQUIRED", "Provide one read revision for every updated source and no other paths.",
                                {"missing": sorted(updates - set(bases)), "unexpected": sorted(set(bases) - updates)})
            snapshot = await self.bridge.call("_source_snapshot", {"documents": [
                {"uri": item.uri, "create": item.create, "base_revision": bases.get(item.uri)} for item in files]})
            plans = build_plan(files, snapshot)
            payload = {key: value for key, value in arguments.items() if key not in {"patch", "base_revisions", "wait_ms"}}
            payload.update(documents=plans, editor_epoch=snapshot["editor_epoch"])
            result = await self.bridge.call("_apply_source_plan", payload)
        if result.get("status") != "pending" or not wait_ms:
            return result
        try:
            detail = await self.operation(result["operation_id"], wait_ms)
        except ToolError as error:
            # Application already began. Preserve the operation identity when
            # a read fails, so transport recovery never suggests replaying it.
            result["result_query_error"] = {"code": error.code, "message": str(error)}
            return result
        final = detail["result"]
        final["operation_id"] = result["operation_id"]
        final["details_retained"] = True
        return final
