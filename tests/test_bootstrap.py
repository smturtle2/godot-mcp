import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("bootstrap", Path(__file__).parents[1] / "scripts/bootstrap.py")
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


def archive(*entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as bundle:
        for name, data in entries:
            bundle.writestr(name, data)
    return stream.getvalue()


def test_select_release_highest_stable_revision_and_exact_version():
    releases = [
        {"tag_name": "v4.7.2_0", "draft": False, "prerelease": False},
        {"tag_name": "v4.7.2_2", "draft": False, "prerelease": False},
        {"tag_name": "v4.7.2_9", "draft": True, "prerelease": False},
        {"tag_name": "v4.7.2_8", "draft": False, "prerelease": True},
        {"tag_name": "v4.6.4_99", "draft": False, "prerelease": False},
    ]
    assert bootstrap.select_release(releases, "4.7.2")["tag_name"] == "v4.7.2_2"
    assert bootstrap.select_release(releases, "4.7.2", "v4.7.2_0")["tag_name"] == "v4.7.2_0"
    with pytest.raises(ValueError, match="No stable release"):
        bootstrap.select_release(releases, "4.7.3")
    with pytest.raises(ValueError, match="No stable release"):
        bootstrap.select_release(releases, "4.7.2", "v4.7.2_8")


def test_safe_extract_accepts_root_and_single_prefixed_directory(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    assert bootstrap.safe_extract(archive(("pyproject.toml", "[project]\n")), root) == root / "source"
    prefixed = tmp_path / "prefixed"
    prefixed.mkdir()
    assert bootstrap.safe_extract(archive(("package/pyproject.toml", "[project]\n")), prefixed) == prefixed / "source/package"


@pytest.mark.parametrize("entry", ["../escape", "/absolute", "dir\\escape"])
def test_safe_extract_rejects_traversal_and_backslash(tmp_path, entry):
    target = tmp_path / "target"
    target.mkdir()
    with pytest.raises(ValueError, match="unsafe"):
        bootstrap.safe_extract(archive((entry, "bad"), ("pyproject.toml", "[project]\n")), target)


def test_safe_extract_rejects_symlink(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as bundle:
        info = zipfile.ZipInfo("link")
        info.external_attr = 0o120777 << 16
        bundle.writestr(info, "target")
    target = tmp_path / "target"
    target.mkdir()
    with pytest.raises(ValueError, match="symlinks"):
        bootstrap.safe_extract(stream.getvalue(), target)


def test_safe_extract_rejects_expanded_size_limit(tmp_path, monkeypatch):
    class HugeEntry:
        filename = "pyproject.toml"
        file_size = 500 * 1024 * 1024 + 1
        external_attr = 0

    class FakeZip:
        def __init__(self, _path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def infolist(self):
            return [HugeEntry()]

    monkeypatch.setattr(bootstrap.zipfile, "ZipFile", FakeZip)
    target = tmp_path / "target"
    target.mkdir()
    with pytest.raises(ValueError, match="size limit"):
        bootstrap.safe_extract(b"zip", target)


def test_main_refuses_checksum_mismatch_before_subprocess(tmp_path, monkeypatch, capsys):
    release = {"tag_name": "v4.7.2_1", "draft": False, "prerelease": False,
               "assets": [{"name": "manifest.json", "browser_download_url": "https://manifest"}]}
    artifact = b"not-the-published-archive"
    manifest = {"schema_version": 1, "version": "v4.7.2_1", "engine": "4.7.2",
                "platforms": {"linux-x86_64": True},
                "artifacts": [{"kind": "source", "url": "https://archive", "size": len(artifact),
                                "sha256": hashlib.sha256(b"different").hexdigest()}]}

    def fake_fetch(url, _limit=0):
        return json.dumps([release]).encode() if "api.github" in url else json.dumps(manifest).encode() if url == "https://manifest" else artifact

    called = []
    monkeypatch.setattr(bootstrap, "fetch", fake_fetch)
    monkeypatch.setattr(bootstrap, "platform_id", lambda: "linux-x86_64")
    monkeypatch.setattr(bootstrap.shutil, "which", lambda _name: "/usr/bin/uv")
    monkeypatch.setattr(bootstrap.subprocess, "call", lambda *args, **kwargs: called.append((args, kwargs)))
    assert bootstrap.main(["--engine", "4.7.2"]) == 1
    assert called == []
    assert "integrity check failed" in capsys.readouterr().err
