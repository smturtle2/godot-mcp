"""Bounded editor-side history of DAP output and exception stops."""
from __future__ import annotations

import time
from collections import deque

from .bridge import ToolError


class RuntimeLogs:
    def __init__(self):
        self.runs: dict[str, dict] = {}
        self.current: dict | None = None

    def begin(self, *, complete: bool = True, error: str | None = None):
        self.current = {"entries": deque(maxlen=2000), "cursor": 0,
                        "captured_from_start": complete, "collection_error": error}

    def bind(self, run_id: str):
        if self.current is not None:
            self.runs[run_id] = self.current
            while len(self.runs) > 8:
                del self.runs[next(iter(self.runs))]

    def receive(self, event: dict):
        if self.current is None:
            return
        body = event.get("body", {})
        if event.get("event") == "output":
            message = body.get("output", "")
            kind = "error" if body.get("category") == "stderr" else "log"
        elif event.get("event") == "stopped" and body.get("reason") == "exception":
            message = body.get("text") or body.get("description") or "Execution stopped on an exception."
            kind = "error"
        else:
            return
        if not message:
            return
        self.current["cursor"] += 1
        self.current["entries"].append({"cursor": self.current["cursor"], "kind": kind,
            "message": message, "uri": body.get("source", {}).get("path", ""),
            "line": body.get("line", 0), "time_usec": time.monotonic_ns() // 1000,
            "count": 1, "event": event["event"]})

    def read(self, arguments: dict) -> dict:
        run = self.runs.get(arguments["run_id"])
        if run is None:
            raise ToolError("LOGS_UNAVAILABLE", "No retained log history for this run. Start the run through this MCP connection to collect output before an error stops it.")
        since, limit = arguments.get("since", 0), arguments.get("limit", 200)
        kinds = arguments.get("kinds", [])
        eligible = [entry for entry in run["entries"] if entry["cursor"] > since
                    and (not kinds or entry["kind"] in kinds)]
        entries = eligible[:limit]
        result = {"entries": entries, "cursor": entries[-1]["cursor"] if len(eligible) > limit else run["cursor"],
                  "has_more": len(eligible) > limit, "dropped": max(0, run["cursor"] - len(run["entries"])),
                  "run_id": arguments["run_id"], "origin": "runtime", "history": True, "current_verdict": False,
                  "captured_from_start": run["captured_from_start"]}
        if run["collection_error"]:
            result["collection_error"] = run["collection_error"]
        return result
