"""Per-user versioned installation with a recoverable project/config transaction."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .client_config import _atomic_write, register_client, register_global_client
from .version import ENGINE_VERSION, PRODUCT_VERSION


def default_home() -> Path:
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'godot-mcp'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'godot-mcp'


def executable_at(environment: Path) -> Path:
    return environment / ('Scripts/godot-mcp.exe' if os.name == 'nt' else 'bin/godot-mcp')


def detect_clients(project: Path | None = None) -> list[dict]:
    home = Path.home()
    choices = [
        {'name': 'Codex', 'path': home / '.codex/config.toml', 'format': 'codex'},
        {'name': 'Cursor', 'path': home / '.cursor/mcp.json', 'format': 'json'},

    ]
    if project:
        choices.append({'name': 'VS Code (project)', 'path': project / '.vscode/mcp.json', 'format': 'vscode'})
    if sys.platform == 'darwin':
        choices.append({'name': 'Claude Desktop', 'path': home / 'Library/Application Support/Claude/claude_desktop_config.json', 'format': 'json'})
    elif os.name == 'nt':
        choices.append({'name': 'Claude Desktop', 'path': Path(os.environ.get('APPDATA', home)) / 'Claude/claude_desktop_config.json', 'format': 'json'})
    return [choice for choice in choices if choice['path'].exists()]


def enable_plugin(source: str) -> str:
    """Edit only the plugin enabled array in project.godot, retaining other settings."""
    plugin = 'res://addons/godot_mcp/plugin.cfg'
    section = re.search(r'(?m)^\[editor_plugins\][ \t]*$', source)
    if not section:
        return source.rstrip() + '\n\n[editor_plugins]\n\nenabled=PackedStringArray(' + json.dumps(plugin) + ')\n'
    start = section.end()
    following = re.search(r'(?m)^\[', source[start:])
    end = start + following.start() if following else len(source)
    body = source[start:end]
    enabled = re.search(r'(?m)^[ \t]*enabled\s*=\s*PackedStringArray\((.*?)\)[ \t]*$', body, re.S)
    if not enabled:
        if re.search(r'(?m)^[ \t]*enabled\s*=', body):
            raise ValueError('Unsupported editor_plugins/enabled syntax; enable the plugin manually.')
        body += '\nenabled=PackedStringArray(' + json.dumps(plugin) + ')\n'
    else:
        # Godot serializes strings with JSON-compatible escaping.
        values = json.loads('[' + enabled.group(1) + ']')
        if plugin not in values:
            values.append(plugin)
        replacement = 'enabled=PackedStringArray(' + ', '.join(json.dumps(v) for v in values) + ')'
        body = body[:enabled.start()] + replacement + body[enabled.end():]
    return source[:start] + body + source[end:]


def check_godot(command: str) -> str:
    result = subprocess.run([command, '--version'], capture_output=True, text=True, timeout=15, check=True)
    match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
    actual = match.group(1) if match else result.stdout.strip()
    if actual != ENGINE_VERSION:
        raise ValueError(f'{PRODUCT_VERSION} requires Godot {ENGINE_VERSION}; detected {actual}. No project changes made.')
    return actual


def prepare_environment(source: Path, home: Path, repair: bool = False) -> tuple[Path, Path]:
    """Build at the final immutable path so uv-generated executable shebangs stay valid."""
    if not (source / 'uv.lock').is_file() or not (source / 'pyproject.toml').is_file():
        raise ValueError('Installation source must contain pyproject.toml and uv.lock.')
    uv = shutil.which('uv')
    if not uv:
        raise ValueError('uv was not found; use the bootstrap installer or install uv first.')
    fingerprint = hashlib.sha256()
    for path in sorted([source / 'uv.lock', source / 'pyproject.toml', *list((source / 'src').rglob('*.py')), *list((source / 'src').rglob('*.gd')), *list((source / 'src').rglob('*.cfg'))]):
        fingerprint.update(path.relative_to(source).as_posix().encode())
        fingerprint.update(path.read_bytes())
    digest = fingerprint.hexdigest()
    if not repair:
        for prior in sorted((home / 'versions').glob(PRODUCT_VERSION + '-*'), reverse=True):
            metadata = prior / 'install.json'
            if metadata.is_file() and json.loads(metadata.read_text()).get('digest') == digest:
                executable = executable_at(prior / 'environment')
                if executable.is_file():
                    subprocess.run([str(executable), 'version'], capture_output=True, check=True)
                    return executable, prior
    version_dir = home / 'versions' / f'{PRODUCT_VERSION}-{time.time_ns()}'
    version_dir.mkdir(parents=True)
    package = version_dir / 'source'
    try:
        shutil.copytree(source, package, ignore=shutil.ignore_patterns('.git', '.venv', '__pycache__', '.pytest_cache', '.ruff_cache', 'dist', '.godot', '.godot-mcp'))
        environment = version_dir / 'environment'
        env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(environment))
        env.pop('VIRTUAL_ENV', None)
        subprocess.run([uv, 'sync', '--project', str(package), '--frozen', '--no-dev', '--no-editable', '--python', '3.13'], env=env, check=True)
        executable = executable_at(environment)
        result = subprocess.run([str(executable), 'version'], capture_output=True, text=True, check=True)
        if PRODUCT_VERSION not in result.stdout:
            raise ValueError('Prepared executable version does not match the installer.')
        (version_dir / 'install.json').write_text(json.dumps({'digest': digest, 'version': PRODUCT_VERSION}))
        return executable, version_dir
    except BaseException:
        shutil.rmtree(version_dir)
        raise


def _restore_file(path: Path, backup: Path | None) -> None:
    if backup is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup, path)


def install_project(project: Path, executable: Path, home: Path, config: Path | None = None,
                    config_format: str = 'json', name: str = 'godot-mcp') -> dict:
    project = project.resolve()
    project_file = project / 'project.godot'
    updated = enable_plugin(project_file.read_text(encoding='utf-8'))
    # Refuse to race an active editor, which can overwrite project/plugin changes.
    endpoint = project / '.godot-mcp/endpoint.json'
    if endpoint.exists():
        from .bridge import EditorBridge, ToolError
        try:
            asyncio.run(EditorBridge(project, timeout=2).call('get_context', {}))
        except ToolError as exc:
            if exc.code != 'EDITOR_DISCONNECTED':
                raise ValueError('Close this project in Godot before installing or updating its plugin.') from exc
        else:
            raise ValueError('Close this project in Godot before installing or updating its plugin.')
    stamp = f'{time.time_ns()}-{hashlib.sha256(str(project).encode()).hexdigest()[:8]}'
    backup = home / 'transactions' / stamp
    backup.mkdir(parents=True)
    os.chmod(backup, 0o700)
    target = project / 'addons/godot_mcp'
    shutil.copy2(project_file, backup / 'project.godot')
    link = project / '.godot-mcp/install.json'
    link_existed = link.exists()
    if link_existed:
        shutil.copy2(link, backup / 'link.json')
    existed = target.exists()
    if existed:
        if target.is_symlink():
            raise ValueError('Refusing to replace a symlinked addon directory.')
        shutil.copytree(target, backup / 'addon')
    config_existed = config is not None and config.exists()
    if config_existed:
        shutil.copy2(config, backup / 'client-config')
    index_path = home / 'projects' / (hashlib.sha256(str(project).encode()).hexdigest() + '.json')
    index_existed = index_path.exists()
    if index_existed:
        shutil.copy2(index_path, backup / 'index.json')
    record = {'index_existed': index_existed, 'project': str(project), 'executable': str(executable), 'version': PRODUCT_VERSION,
              'addon_existed': existed, 'link_existed': link_existed, 'config': str(config.resolve()) if config else None,
              'config_existed': config_existed, 'backup': str(backup), 'status': 'prepared'}
    (backup / 'transaction.json').write_text(json.dumps(record, indent=2))
    try:
        staged = Path(tempfile.mkdtemp(prefix='.godot-mcp-', dir=project))
        try:
            shutil.copytree(Path(__file__).parent / 'addon', staged / 'addon')
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged / 'addon'), target)
        finally:
            shutil.rmtree(staged)
        project_file.write_text(updated, encoding='utf-8')
        _atomic_write(link, json.dumps({'home': str(home.resolve()), 'version': PRODUCT_VERSION}))
        registration = register_client(config, name, executable, project, config_format) if config else {
            'settings': {'command': str(executable), 'args': ['serve', '--project', str(project)]}}
        record.update(status='installed', registration=registration)
        (backup / 'transaction.json').write_text(json.dumps(record, indent=2))
        index = home / 'projects'
        index.mkdir(exist_ok=True)
        (index / (hashlib.sha256(str(project).encode()).hexdigest() + '.json')).write_text(json.dumps(record, indent=2))
        return record
    except BaseException:
        shutil.copy2(backup / 'project.godot', project_file)
        if target.exists():
            shutil.rmtree(target)
        if existed:
            shutil.copytree(backup / 'addon', target)
        if config:
            _restore_file(config, backup / 'client-config' if config_existed else None)
        _restore_file(link, backup / 'link.json' if link_existed else None)
        record['status'] = 'rolled_back'
        (backup / 'transaction.json').write_text(json.dumps(record, indent=2))
        raise


def install_global(executable: Path, home: Path, project: Path | None = None,
                   config: Path | None = None, config_format: str = 'json', name: str = 'godot-mcp') -> dict:
    """Activate a tested environment, refresh linked plugins and saved registrations atomically."""
    home.mkdir(parents=True, exist_ok=True)
    os.chmod(home, 0o700)
    clients_file, active_file = home / 'clients.json', home / 'active.json'
    clients = json.loads(clients_file.read_text()) if clients_file.exists() else []
    if config:
        config = config.expanduser().resolve()
        clients = [c for c in clients if not (c['path'] == str(config) and c['name'] == name)]
        clients.append({'path': str(config), 'name': name, 'format': config_format})
    projects = {Path(json.loads(p.read_text())['project']) for p in (home / 'projects').glob('*.json')}
    projects = {p for p in projects if (p / 'project.godot').is_file()}
    if project:
        projects.add(project.resolve())
    backup = home / 'transactions' / f'{time.time_ns()}-global'
    backup.mkdir(parents=True)
    os.chmod(backup, 0o700)
    snapshots = []
    for index, path in enumerate([clients_file, active_file, *[Path(c['path']) for c in clients]]):
        destination = backup / f'file-{index}'
        if path.exists():
            shutil.copy2(path, destination)
        snapshots.append({'path': str(path), 'backup': str(destination) if path.exists() else None})
    record = {'kind': 'global', 'version': PRODUCT_VERSION, 'executable': str(executable),
              'backup': str(backup), 'snapshots': snapshots, 'children': [], 'status': 'prepared'}
    journal = backup / 'transaction.json'
    journal.write_text(json.dumps(record, indent=2))
    try:
        for linked in sorted(projects):
            child = install_project(linked, executable, home)
            record['children'].append(child['backup'])
            journal.write_text(json.dumps(record, indent=2))
        registrations = [register_global_client(Path(c['path']), c['name'], executable, home, c['format']) for c in clients]
        if not registrations:
            registrations = [{'settings': {'command': str(executable), 'args': ['connect', '--home', str(home)]}}]
        _atomic_write(clients_file, json.dumps(clients, indent=2))
        _atomic_write(active_file, json.dumps({'version': PRODUCT_VERSION, 'executable': str(executable)}, indent=2))
        record.update(status='installed', registrations=registrations)
        journal.write_text(json.dumps(record, indent=2))
        return record
    except BaseException:
        rollback(backup)
        raise


def rollback(transaction: Path) -> dict:
    backup = transaction if transaction.is_dir() else transaction.parent
    record = json.loads((backup / 'transaction.json').read_text())
    if record.get('kind') == 'global':
        for child in reversed(record['children']):
            rollback(Path(child))
        for item in reversed(record['snapshots']):
            _restore_file(Path(item['path']), Path(item['backup']) if item['backup'] else None)
        record['status'] = 'rolled_back'
        (backup / 'transaction.json').write_text(json.dumps(record, indent=2))
        return record
    project = Path(record['project'])
    # Explicit rollback restores precisely the selected pre-install snapshot.
    target = project / 'addons/godot_mcp'
    shutil.copy2(backup / 'project.godot', project / 'project.godot')
    if target.exists():
        shutil.rmtree(target)
    if record['addon_existed']:
        shutil.copytree(backup / 'addon', target)
    if record['config']:
        _restore_file(Path(record['config']), backup / 'client-config' if record['config_existed'] else None)
    _restore_file(project / '.godot-mcp/install.json', backup / 'link.json' if record.get('link_existed') else None)
    index = backup.parent.parent / 'projects' / (hashlib.sha256(str(project).encode()).hexdigest() + '.json')
    _restore_file(index, backup / 'index.json' if record.get('index_existed') else None)
    record['status'] = 'rolled_back'
    (backup / 'transaction.json').write_text(json.dumps(record, indent=2))
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='godot-mcp install')
    parser.add_argument('--project', type=Path)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--home', type=Path, default=default_home())
    parser.add_argument('--godot', default=shutil.which('godot') or shutil.which('godot4') or 'godot')
    parser.add_argument('--client-config', type=Path)
    parser.add_argument('--client-format', choices=['json', 'codex', 'vscode'], default='json')
    parser.add_argument('--name', default='godot-mcp')
    parser.add_argument('--yes', action='store_true', help='accept explicit/default values without prompts')
    parser.add_argument('--repair', action='store_true', help='prepare a fresh environment even if this version is installed')
    parser.add_argument('--plugin-only', action='store_true', help='reuse this installed executable; no environment preparation')
    parser.add_argument('--rollback', type=Path, help='restore a selected installation transaction snapshot')
    args = parser.parse_args(argv)
    try:
        if args.rollback:
            print(json.dumps(rollback(args.rollback), indent=2))
            return 0
        if not args.yes:
            # /dev/tty supports curl | sh; stdin supports explicitly piped answers.
            with contextlib.ExitStack() as stack:
                terminal = sys.stdin
                if not sys.stdin.isatty() and os.name != 'nt':
                    with contextlib.suppress(OSError):
                        terminal = stack.enter_context(open('/dev/tty', encoding='utf-8'))
                def ask(label, default):
                    print(f'{label} [{default}]: ', end='', flush=True)
                    line = terminal.readline()
                    if not line:
                        raise ValueError('No interactive input. Use --yes for non-interactive installation.')
                    return line.strip() or str(default)
                chosen_project = ask('Project to link now, or later', args.project or 'later')
                args.project = None if chosen_project.lower() == 'later' else Path(chosen_project).expanduser()
                args.godot = ask('Godot executable', args.godot)
                args.home = Path(ask('Installation directory', args.home)).expanduser()
                clients = detect_clients(args.project)
                suggested = str(args.client_config or (clients[0]['path'] if clients else 'manual'))
                chosen = ask('MCP configuration file, or manual', suggested)
                args.client_config = None if chosen.lower() == 'manual' else Path(chosen).expanduser()
                if args.client_config:
                    suggested_format = next((c['format'] for c in clients if c['path'] == args.client_config), args.client_format)
                    args.client_format = ask('Config format (json/codex/vscode)', suggested_format)
                print(f'Install {PRODUCT_VERSION} for Godot {ENGINE_VERSION} on {platform.system()} {platform.machine()}\nProject: {args.project}\nLocation: {args.home}\nClient: {args.client_config or "manual settings"}')
                if ask('Continue? (yes/no)', 'yes').lower() not in ('y', 'yes'):
                    print('Cancelled; no changes made.')
                    return 0
        if args.project is not None:
            if not (args.project / 'project.godot').is_file():
                raise ValueError('--project must contain project.godot.')
            args.project = args.project.resolve()
        if args.plugin_only and args.project is None:
            raise ValueError('--plugin-only requires --project.')
        check_godot(args.godot)
        args.home = args.home.expanduser().resolve()
        if args.plugin_only:
            executable = executable_at(Path(sys.prefix))
            if not executable.is_file():
                raise ValueError('Current environment has no godot-mcp executable.')
        else:
            executable, _ = prepare_environment(args.source.resolve(), args.home, args.repair)
        if args.plugin_only:
            active_file = args.home / 'active.json'
            if active_file.exists():
                active = json.loads(active_file.read_text())
                executable = Path(active['executable'])
                if active['version'] != PRODUCT_VERSION:
                    raise ValueError('Run plugin linking from the active installed executable.')
            record = install_project(args.project, executable, args.home)
            print(f'Linked {args.project}. Open it in Godot {ENGINE_VERSION}.')
            print(f'Rollback: "{executable}" install --rollback "{record["backup"]}"')
        else:
            record = install_global(executable, args.home, args.project, args.client_config, args.client_format, args.name)
            print(f'Installed {PRODUCT_VERSION} for this user. Restart your MCP client to load it.')
            print(json.dumps(record['registrations'], indent=2))
            print(f'Link another project: "{executable}" install --plugin-only --yes --home "{args.home}" --project PATH')
            print(f'Rollback: "{executable}" install --rollback "{record["backup"]}"')
        if args.project:
            print(f'Open {args.project} in Godot {ENGINE_VERSION}; then run "{executable}" check --project "{args.project}".')
        print('Installation is complete; editor connection is verified separately.')
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'Installation failed: {exc}', file=sys.stderr)
        return 1
