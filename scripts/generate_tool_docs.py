"""Generate Markdown reference documentation from the executable tool catalog."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def render() -> str:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from godot_mcp.catalog import TOOL_SPECS

    lines = ["# Godot MCP tool reference", "", "Generated from [`TOOL_SPECS`](../src/godot_mcp/catalog.py). The canonical JSON input schemas are served by MCP `tools/list`; this page keeps the discoverable catalog compact.", "", "`install_plugin` can install and enable the project plugin before an editor connection exists. After opening the project, use `get_context` for live editor state.", "", "| Tool | Description |", "|---|---|"]
    for spec in TOOL_SPECS:
        lines.append(f"| `{spec['name']}` | {spec['description']} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if docs/tools.md differs from generated output")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = root / "docs/tools.md"
    content = render()
    if args.check:
        if not target.exists() or target.read_text() != content:
            print(f"Generated tool docs are out of date: {target}", file=sys.stderr)
            return 1
        print("Tool documentation is synchronized.")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    print(f"Generated {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
