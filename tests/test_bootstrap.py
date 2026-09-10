import hashlib
import io
import json
import zipfile

import pytest

from godot_mcp import bootstrap


def archive(*entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as bundle:
        for name, data in entries:
            bundle.writestr(name, data)
    return stream.getvalue()


@pytest.mark.parametrize("release", [
    {"tag_name": "v4.7.2_0", "draft": True, "prerelease": False},
    {"tag_name": "v4.7.2_0", "draft": False, "prerelease": True},
    {"tag_name": "4.7.2_0", "draft": False, "prerelease": False},
    {"tag_name": "v4.7_0", "draft": False, "prerelease": False},
])
def test_validate_release_rejects_unstable_or_invalid_tags(release):
    with pytest.raises(ValueError):
        bootstrap.validate_release(release)


def test_validate_release_returns_engine_from_stable_tag():
    assert bootstrap.validate_release({"tag_name": "v4.7.2_3", "draft": False, "prerelease": False}) == "4.7.2"


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
        return json.dumps(release).encode() if url.endswith("/latest") else json.dumps(manifest).encode() if url == "https://manifest" else artifact

    called = []
    monkeypatch.setattr(bootstrap, "fetch", fake_fetch)
    monkeypatch.setattr(bootstrap, "platform_id", lambda: "linux-x86_64")
    monkeypatch.setattr(bootstrap.shutil, "which", lambda _name: "/usr/bin/uv")
    monkeypatch.setattr(bootstrap.subprocess, "call", lambda *args, **kwargs: called.append((args, kwargs)))
    assert bootstrap.main([]) == 1
    assert called == []
    assert "integrity check failed" in capsys.readouterr().err


def test_main_latest_release_never_discovers_godot_and_invokes_locked_uv(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    artifact = b"archive"
    release = {"tag_name": "v4.7.2_1", "draft": False, "prerelease": False,
               "assets": [{"name": "manifest.json", "browser_download_url": "https://manifest"}]}
    manifest = {"schema_version": 1, "version": release["tag_name"], "engine": "4.7.2",
                "platforms": {"linux-x86_64": True}, "artifacts": [{"kind": "source", "url": "https://archive",
                "size": len(artifact), "sha256": hashlib.sha256(artifact).hexdigest()}]}
    calls = []

    def fetch(url, _limit=0):
        return json.dumps(release).encode() if url.endswith("/latest") else json.dumps(manifest).encode() if url == "https://manifest" else artifact

    monkeypatch.setattr(bootstrap, "fetch", fetch)
    monkeypatch.setattr(bootstrap, "platform_id", lambda: "linux-x86_64")
    monkeypatch.setattr(bootstrap.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else pytest.fail("Godot discovery invoked"))
    monkeypatch.setattr(bootstrap, "safe_extract", lambda data, target: source)
    monkeypatch.setattr(bootstrap.subprocess, "call", lambda command, **kwargs: calls.append((command, kwargs)) or 0)
    assert bootstrap.main(["--yes", "--project", "/tmp/project"]) == 0
    assert calls and "--frozen" in calls[0][0] and "--link-mode" in calls[0][0]
