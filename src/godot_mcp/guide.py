"""Bundled manual and its section index; independent of project/editor state."""
from __future__ import annotations

from importlib.resources import files

from .version import ENGINE_VERSION, PRODUCT_VERSION

GUIDE_SECTIONS = {
    "start": ("Start here", "Capabilities, connection, project selection, and support limits."),
    "development": ("Godot development", "Technical choices for scenes, resources, signals, UI, animation, and worlds."),
    "model": ("Editor concepts", "Editor, file, and runtime state; references, values, sharing, and imports."),
    "work": ("Using Godot MCP", "Task-based usage and examples for editing, running, debugging, and exporting."),
    "recovery": ("Recovery", "Incomplete operations, conflicts, saving, Undo, restoration, and connection failures."),
    "tools": ("Tool choices", "Tool roles, selection criteria, and current usage distinctions."),
}


def read_guide(section: str | None = None) -> str:
    header = f"Godot MCP {PRODUCT_VERSION} · Godot {ENGINE_VERSION}"
    if section is None:
        lines = ["# Godot MCP guide", "", header, "",
                 "Inspect, edit, run, and debug Godot projects through the live editor.",
                 "Select a section to read its English content.", "",
                 "| Section | Content |", "|---|---|"]
        for name, (title, description) in GUIDE_SECTIONS.items():
            lines.append(f"| `{name}` | **{title}.** {description} |")
        return "\n".join(lines) + "\n"

    # Only registered identifiers can select a bundled file.
    GUIDE_SECTIONS[section]
    body = files("godot_mcp").joinpath("guide_content", f"{section}.md").read_text(encoding="utf-8")
    if section == "tools":
        from .catalog import TOOL_SPECS

        lines = [body.rstrip(), "", "## Current tool catalog", "",
                 "Argument schemas are published in MCP tools/list.", "",
                 "| Tool | Description |", "|---|---|"]
        for spec in TOOL_SPECS:
            description = spec["description"].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| `{spec['name']}` | {description} |")
        body = "\n".join(lines) + "\n"
    return f"{header} · Section: {section}\n\n{body}"
