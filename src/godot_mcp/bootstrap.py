#!/usr/bin/env python3
"""Download the latest stable release, verify its archive, and run its locked installer."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

REPOSITORY = 'smturtle2/godot-mcp'
API = f'https://api.github.com/repos/{REPOSITORY}/releases'


def installation_environment(environment: Path | None = None) -> dict[str, str]:
    """Isolate only installer subprocesses, retaining proxy/cache/index preferences."""
    env = dict(os.environ)
    for key in ('VIRTUAL_ENV', 'UV_PROJECT_ENVIRONMENT', 'PYTHONPATH'):
        env.pop(key, None)
    if environment is not None:
        env['UV_PROJECT_ENVIRONMENT'] = str(environment)
    return env


def fetch(url: str, limit: int = 100 * 1024 * 1024) -> bytes:
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise ValueError('Release downloads require HTTPS.')
    request = urllib.request.Request(url, headers={'User-Agent': 'godot-mcp-installer', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        if urllib.parse.urlsplit(response.url).scheme != 'https':
            raise ValueError('Refusing a non-HTTPS redirect.')
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Release download exceeds size limit.')
    return data


def platform_id() -> str:
    system = {'Linux': 'linux', 'Darwin': 'macos', 'Windows': 'windows'}.get(platform.system())
    machine = {'AMD64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine(), platform.machine())
    return f'{system}-{machine}'


def validate_release(release: dict) -> str:
    """Validate GitHub's latest stable release and return its engine metadata."""
    match = re.fullmatch(r'v(\d+\.\d+\.\d+)_(\d+)', release.get('tag_name', ''))
    if not match or release.get('draft') or release.get('prerelease'):
        raise ValueError('Latest release is not a supported stable Godot MCP release.')
    return match[1]


def safe_extract(data: bytes, target: Path) -> Path:
    archive = target / 'download.zip'
    archive.write_bytes(data)
    source = target / 'source'
    source.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        total = 0
        for entry in bundle.infolist():
            path = (source / entry.filename).resolve()
            if not path.is_relative_to(source.resolve()) or '\\' in entry.filename:
                raise ValueError('Archive contains unsafe paths.')
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Archive contains symlinks.')
            total += entry.file_size
            if total > 500 * 1024 * 1024:
                raise ValueError('Expanded archive exceeds size limit.')
        bundle.extractall(source)
    if (source / 'pyproject.toml').is_file():
        return source
    children = list(source.iterdir())
    if len(children) == 1 and (children[0] / 'pyproject.toml').is_file():
        return children[0]
    raise ValueError('Release does not contain an installable locked source package.')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--source', type=Path, help='install a local source checkout without downloading a release')
    args, remaining = parser.parse_known_args(argv)
    try:
        uv = shutil.which('uv')
        if not uv:
            raise ValueError('uv is required. Run install.sh/install.ps1 or install uv first.')
        if args.source:
            source = args.source.resolve()
            return subprocess.call([uv, 'run', '--project', str(source), '--frozen', '--no-dev', '--link-mode', 'copy', 'godot-mcp', 'install', '--source', str(source), *remaining], env=installation_environment())
        release = json.loads(fetch(API + '/latest', 5 * 1024 * 1024))
        engine = validate_release(release)
        manifest_asset = next((a for a in release['assets'] if a['name'] == 'manifest.json'), None)
        if manifest_asset is None:
            raise ValueError('Release has no installation manifest.')
        manifest = json.loads(fetch(manifest_asset['browser_download_url'], 1024 * 1024))
        if manifest.get('schema_version') != 1 or manifest.get('version') != release['tag_name'] or manifest.get('engine') != engine:
            raise ValueError('Release manifest version is inconsistent.')
        if platform_id() not in manifest['platforms']:
            raise ValueError(f'No compatible source package for {platform_id()}.')
        artifact = next(a for a in manifest['artifacts'] if a['kind'] == 'source')
        print(f"Selected {manifest['version']} for Godot {engine} / {platform_id()}", flush=True)
        data = fetch(artifact['url'])
        if len(data) != artifact['size'] or hashlib.sha256(data).hexdigest() != artifact['sha256']:
            raise ValueError('Release archive integrity check failed; nothing installed.')
        with tempfile.TemporaryDirectory(prefix='godot-mcp-install-') as directory:
            source = safe_extract(data, Path(directory))
            # Both the bootstrap environment and final installation honor the release lock.
            return subprocess.call([uv, 'run', '--project', str(source), '--frozen', '--no-dev', '--link-mode', 'copy', 'godot-mcp', 'install', '--source', str(source), *remaining], env=installation_environment())
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(f'Installation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
