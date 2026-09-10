"""Generate Markdown reference documentation from the executable tool catalog."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def render() -> str:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from godot_mcp.catalog import TOOL_SPECS

    lines = ["# Godot MCP tool reference", "", "Generated from `godot_mcp.catalog.TOOL_SPECS`; schemas are JSON Schema Draft 2020-12.", "",
             "| # | Tool | Description |", "|---:|---|---|"]
    for index, spec in enumerate(TOOL_SPECS, 1):
        lines.append(f"| {index} | `{spec['name']}` | {spec['description']} |")
    lines += ["", "## Full input schemas", ""]
    for index, spec in enumerate(TOOL_SPECS, 1):
        schema = json.dumps(spec["inputSchema"], ensure_ascii=False, indent=2, sort_keys=True)
        lines += ["<details>", f"<summary>{index}. <code>{spec['name']}</code></summary>", "", "```json", schema, "```", "", "</details>", ""]
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
