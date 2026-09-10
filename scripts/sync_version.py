"""Synchronize the Python product version into the Godot addon metadata."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def values(root: Path) -> tuple[str, str, str]:
    sys.path.insert(0, str(root / "src"))
    from godot_mcp.version import ENGINE_VERSION, PRODUCT_VERSION, PROTOCOL_VERSION

    return ENGINE_VERSION, PRODUCT_VERSION, PROTOCOL_VERSION


def expected(root: Path) -> tuple[Path, str, Path, str]:
    engine, product, protocol = values(root)
    version = root / "src/godot_mcp/addon/version.gd"
    version_text = ("# Generated from godot_mcp.version by scripts/sync_version.py.\n"
                    "extends RefCounted\n"
                    f'const PRODUCT := "{product}"\n'
                    f'const ENGINE := "{engine}"\n'
                    f'const PROTOCOL := "{protocol}"\n')
    cfg = root / "src/godot_mcp/addon/plugin.cfg"
    current = cfg.read_text()
    replacement = f'version="{product}"'
    if re.search(r'^version=".*"$', current, re.MULTILINE):
        cfg_text = re.sub(r'^version=".*"$', replacement, current, count=1, flags=re.MULTILINE)
    else:
        raise RuntimeError(f"{cfg} has no version= entry")
    return version, version_text, cfg, cfg_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if addon metadata is out of date")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version, version_text, cfg, cfg_text = expected(root)
    drift = []
    if not version.exists() or version.read_text() != version_text:
        drift.append(str(version))
    if not cfg.exists() or cfg.read_text() != cfg_text:
        drift.append(str(cfg))
    if args.check:
        if drift:
            print("Version metadata out of date: " + ", ".join(drift), file=sys.stderr)
            return 1
        print("Version metadata is synchronized.")
        return 0
    version.parent.mkdir(parents=True, exist_ok=True)
    version.write_text(version_text)
    cfg.write_text(cfg_text)
    print("Synchronized " + str(version) + " and " + str(cfg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
