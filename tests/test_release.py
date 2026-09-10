import hashlib
import json
import zipfile
from pathlib import Path

from godot_mcp.version import ENGINE_VERSION, PRODUCT_VERSION, PROTOCOL_VERSION
from scripts.build_release import build


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_source_bundle_is_reproducible_and_safe(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_zip = build(first, skip_wheel=True)
    second_zip = build(second, skip_wheel=True)
    assert _digest(first_zip) == _digest(second_zip)
    with zipfile.ZipFile(first_zip) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names)
        assert "src/godot_mcp/version.py" in names
        assert "uv.lock" in names
        assert "tests/test_release.py" in names
        assert ".venv/bin/python" not in names


def test_manifest_describes_hashed_source(tmp_path):
    output = tmp_path / "release"
    source = build(output, skip_wheel=True)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["version"] == PRODUCT_VERSION
    assert manifest["engine"] == ENGINE_VERSION
    assert manifest["protocol"] == PROTOCOL_VERSION
    assert manifest["python"] == "3.13"
    assert manifest["platforms"] == [
        "linux-x86_64", "linux-aarch64", "macos-x86_64", "macos-aarch64", "windows-x86_64"
    ]
    artifact = manifest["artifacts"][0]
    assert artifact["kind"] == "source"
    assert artifact["filename"] == source.name
    assert artifact["sha256"] == _digest(source)
    assert artifact["size"] == source.stat().st_size
    assert artifact["url"].endswith(f"/{PRODUCT_VERSION}/{source.name}")
