"""Generate Markdown reference documentation from the executable tool catalog."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def render() -> str:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from godot_mcp.guide import read_guide

    return read_guide("tools")


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
