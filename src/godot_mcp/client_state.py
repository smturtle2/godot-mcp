"""Defaults from this client's observations, never from unobserved editor state."""
from __future__ import annotations

import copy

from .bridge import ToolError
from .source_patch import parse_patch

RUNTIME_TOOLS = {"send_input", "wait_for_condition", "sample_performance", "stop_game",
                 "inspect_debugger", "debug_control", "inspect_runtime"}


class ClientState:
    def __init__(self):
        self.selected_project = None
        self.projects: dict[str, dict] = {}

    def prepare(self, project: str, name: str, arguments: dict) -> dict:
        state = self.projects.setdefault(project, {"bases": {}, "run_id": None, "epoch": None})
        arguments = copy.deepcopy(arguments)
        if name == "apply_script_changes" and "base_revisions" not in arguments:
            updated = [item.uri for item in parse_patch(arguments["patch"]) if not item.create]
            arguments["base_revisions"] = {uri: state["bases"][uri] for uri in updated if uri in state["bases"]}
        runtime = name in RUNTIME_TOOLS or (name == "capture_viewport" and arguments["viewport"]["kind"] == "game")
        if name == "get_logs" and arguments.pop("origin", "editor") == "runtime":
            runtime = True
        if runtime:
            target = (arguments["node"] if name == "inspect_runtime" else
                      arguments["viewport"] if name == "capture_viewport" else arguments)
            run_id = target.get("run_id") or state["run_id"]
            if not run_id:
                raise ToolError("RUN_REQUIRED", "Start a run or read get_context before omitting run_id.")
            target.setdefault("run_id", run_id)
            # Conditions/observations inherit this request's selected run.
            def fill(value):
                if isinstance(value, dict):
                    if isinstance(value.get("path"), str) and value["path"].startswith("/root"):
                        value.setdefault("run_id", run_id)
                    for child in value.values():
                        fill(child)
                elif isinstance(value, list):
                    for child in value:
                        fill(child)
            fill(arguments)
        return arguments

    def observe(self, project: str, name: str, result: dict):
        state = self.projects.setdefault(project, {"bases": {}, "run_id": None, "epoch": None})
        epoch = result.get("editor_epoch")
        if epoch and epoch != state["epoch"]:
            state.update(bases={}, run_id=None, epoch=epoch)
        if name in {"read_scripts", "apply_script_changes"} and not result.get("preview"):
            for document in result.get("documents", []):
                if document.get("revision") and not document.get("error"):
                    state["bases"][document["uri"]] = document["revision"]
            while len(state["bases"]) > 256:
                del state["bases"][next(iter(state["bases"]))]
        if name in {"get_context", "run_scene"} and result.get("run_id"):
            state["run_id"] = result["run_id"]
        self.selected_project = project
