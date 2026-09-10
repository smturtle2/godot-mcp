"""Build a reproducible source bundle and release manifest."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

from godot_mcp.version import ENGINE_VERSION, PRODUCT_VERSION, PROTOCOL_VERSION

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = [
    "linux-x86_64",
    "linux-aarch64",
    "macos-x86_64",
    "macos-aarch64",
    "windows-x86_64",
]
INCLUDE = ("README.md", "LICENSE", "CHANGELOG.md", ".github", ".gitignore", "pyproject.toml", "uv.lock", ".python-version", "install.sh", "install.ps1", "docs", "scripts", "src", "tests")
EXCLUDE_PARTS = {".git", ".venv", ".pytest_cache", ".ruff_cache", "__pycache__", ".mypy_cache"}


def _epoch() -> int:
    value = os.environ.get("SOURCE_DATE_EPOCH")
    if value is not None:
        return int(value)
    return int(subprocess.check_output(["git", "log", "-1", "--format=%ct"], cwd=ROOT, text=True).strip())


def _files() -> list[Path]:
    paths: list[Path] = []
    for entry in INCLUDE:
        path = ROOT / entry
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(p for p in path.rglob("*") if p.is_file())
    return sorted(
        (p for p in paths if not (EXCLUDE_PARTS & set(p.relative_to(ROOT).parts))),
        key=lambda p: p.relative_to(ROOT).as_posix(),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip(output: Path, timestamp: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    date = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    date_time = (max(1980, date.year), date.month, date.day, date.hour, date.minute, date.second)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in _files():
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def build(output: Path, skip_wheel: bool = False) -> Path:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    timestamp = _epoch()
    source_name = f"godot-mcp-{PRODUCT_VERSION}.zip"
    source_path = output / source_name
    _zip(source_path, timestamp)

    artifacts = [
        {
            "kind": "source",
            "filename": source_name,
            "url": f"https://github.com/smturtle2/godot-mcp/releases/download/{PRODUCT_VERSION}/{source_name}",
            "sha256": _sha256(source_path),
            "size": source_path.stat().st_size,
        }
    ]
    if not skip_wheel:
        subprocess.run(["uv", "build", "--wheel", "--out-dir", str(output)], cwd=ROOT, check=True)
        wheels = sorted(output.glob("*.whl"))
        if not wheels:
            raise RuntimeError("uv build did not produce a wheel")
        wheel = wheels[-1]
        artifacts.append(
            {
                "kind": "wheel",
                "filename": wheel.name,
                "url": f"https://github.com/smturtle2/godot-mcp/releases/download/{PRODUCT_VERSION}/{wheel.name}",
                "sha256": _sha256(wheel),
                "size": wheel.stat().st_size,
            }
        )
    manifest = {
        "schema_version": 1,
        "version": PRODUCT_VERSION,
        "engine": ENGINE_VERSION,
        "protocol": PROTOCOL_VERSION,
        "python": "3.13",
        "platforms": PLATFORMS,
        "artifacts": artifacts,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return source_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "release")
    parser.add_argument("--skip-wheel", action="store_true")
    args = parser.parse_args()
    build(args.output, args.skip_wheel)


if __name__ == "__main__":
    main()
