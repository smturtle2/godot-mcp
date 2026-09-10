#!/usr/bin/env python3
"""Download a compatible release, verify its archive, and run its locked installer."""
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


def godot_candidates() -> list[str]:
    """Use configured commands and standard app locations; never scan whole disks."""
    candidates = []
    if os.environ.get('GODOT'):
        candidates.append(os.environ['GODOT'])
    for name in ('godot', 'godot4', 'godot-mono', 'Godot'):
        command = shutil.which(name)
        if command:
            candidates.append(command)
    if sys.platform == 'darwin':
        for directory in (Path('/Applications'), Path.home() / 'Applications'):
            for bundle in sorted(directory.glob('Godot*.app')):
                candidates.append(str(bundle / 'Contents/MacOS/Godot'))
    elif os.name == 'nt':
        for directory in (Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Programs/Godot',
                          Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Godot'):
            candidates.extend(str(p) for p in sorted(directory.glob('Godot*.exe')))
    else:
        for directory in (Path.home() / '.local/bin', Path('/usr/local/bin'), Path('/usr/bin')):
            candidates.extend(str(directory / name) for name in ('godot', 'godot4') if (directory / name).is_file())
    return list(dict.fromkeys(candidates))


def probe_godot(command: str, expected: str | None = None) -> tuple[str, str]:
    command = command.strip()
    if len(command) >= 2 and command[0] == command[-1] and command[0] in ('"', "'"):
        command = command[1:-1]
    path = Path(command).expanduser()
    if path.suffix.lower() == '.app':
        path = path / 'Contents/MacOS/Godot'
    executable = shutil.which(str(path)) or str(path.resolve())
    result = subprocess.run([executable, '--version'], text=True, capture_output=True, timeout=10, check=True)
    match = re.search(r'(?m)^(\d+\.\d+\.\d+)\.(?:stable|dev|alpha|beta|rc)', result.stdout.strip())
    if not match:
        raise ValueError('The selected executable did not return a recognizable Godot version.')
    version = match[1]
    if expected and version != expected:
        raise ValueError(f'Godot {expected} is required; detected {version}.')
    return executable, version


def _prompt_godot() -> str:
    import contextlib
    with contextlib.ExitStack() as stack:
        terminal = sys.stdin
        if not sys.stdin.isatty() and os.name != 'nt':
            with contextlib.suppress(OSError):
                terminal = stack.enter_context(open('/dev/tty', encoding='utf-8'))
        print('Godot executable path (blank to cancel): ', end='', flush=True)
        line = terminal.readline()
        if not line.strip():
            raise ValueError('No Godot path provided. Use --godot PATH for unattended installation.')
        return line.strip()


def resolve_godot(command: str | None = None, *, expected: str | None = None,
                  interactive: bool = True, prompt=None) -> tuple[str, str]:
    errors = []
    for candidate in ([command] if command else godot_candidates()):
        try:
            return probe_godot(candidate, expected)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            errors.append(str(exc))
    detail = f' {errors[-1]}' if errors else ''
    if not interactive:
        raise ValueError('Could not find a usable Godot executable. Supply --godot PATH.' + detail)
    print('Godot automatic detection failed.' + detail, file=sys.stderr)
    while True:
        candidate = (prompt or _prompt_godot)()
        if not candidate.strip():
            raise ValueError('Godot path entry cancelled.')
        try:
            return probe_godot(candidate, expected)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print(f'Cannot use this Godot executable: {exc}', file=sys.stderr)


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


def select_release(releases: list[dict], engine: str, version: str | None = None) -> dict:
    candidates = []
    for release in releases:
        tag = release.get('tag_name', '')
        match = re.fullmatch(r'v(\d+\.\d+\.\d+)_(\d+)', tag)
        if not match or release.get('draft') or release.get('prerelease'):
            continue
        if match[1] == engine and (version is None or tag == version):
            candidates.append((int(match[2]), release))
    if not candidates:
        raise ValueError(f'No stable release is compatible with Godot {engine}' + (f' ({version})' if version else '') + '.')
    return max(candidates, key=lambda item: item[0])[1]


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
    parser.add_argument('--version')
    parser.add_argument('--engine')
    parser.add_argument('--godot')
    parser.add_argument('--source', type=Path, help='install a local source checkout without downloading a release')
    args, remaining = parser.parse_known_args(argv)
    try:
        uv = shutil.which('uv')
        if not uv:
            raise ValueError('uv is required. Run install.sh/install.ps1 or install uv first.')
        if args.source:
            source = args.source.resolve()
            godot_args = ['--godot', args.godot] if args.godot else []
            return subprocess.call([uv, 'run', '--project', str(source), '--frozen', '--no-dev', '--link-mode', 'copy', 'godot-mcp', 'install', '--source', str(source), *godot_args, *remaining], env=installation_environment())
        engine = args.engine
        if not engine or args.godot:
            args.godot, detected_engine = resolve_godot(args.godot, expected=engine, interactive='--yes' not in remaining)
            engine = engine or detected_engine
            print(f'Godot: {args.godot} ({engine})', flush=True)
        releases = json.loads(fetch(API + '?per_page=100', 5 * 1024 * 1024))
        release = select_release(releases, engine, args.version)
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
            godot_args = ['--godot', args.godot] if args.godot else []
            return subprocess.call([uv, 'run', '--project', str(source), '--frozen', '--no-dev', '--link-mode', 'copy', 'godot-mcp', 'install', '--source', str(source), *godot_args, *remaining], env=installation_environment())
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError, zipfile.BadZipFile) as exc:
        print(f'Installation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
