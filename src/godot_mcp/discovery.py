"""Discover editor instances registered with a user-wide installation."""
from __future__ import annotations

import json
from pathlib import Path

import psutil

from .bridge import EditorBridge, ToolError
from .version import ENGINE_VERSION, PRODUCT_VERSION, PROTOCOL_VERSION


class EditorDirectory:
    def __init__(self, home: Path):
        self.home = home.resolve()
        self.bridges: dict[Path, EditorBridge] = {}

    def projects(self) -> list[dict]:
        found = []
        for file in sorted((self.home / 'editors').glob('*.json')):
            try:
                registered = json.loads(file.read_text())
                project = Path(registered['project']).resolve()
                if project not in self.bridges:
                    self.bridges[project] = EditorBridge(project)
                bridge = self.bridges[project]
                endpoint = bridge.endpoint()
                if endpoint.get('epoch') != registered.get('epoch'):
                    continue
                if not psutil.pid_exists(int(endpoint.get('pid', 0))):
                    continue
                found.append({'project': str(project), 'version': endpoint['version'],
                              'engine': ENGINE_VERSION, 'editor_pid': endpoint['pid']})
            except (OSError, ValueError, KeyError, TypeError, ToolError):
                continue
        return found

    def select(self, project: str | None) -> EditorBridge:
        projects = self.projects()
        if project:
            selected = Path(project).expanduser().resolve()
            if not any(Path(p['project']) == selected for p in projects):
                raise ToolError('PROJECT_CLOSED', 'The selected project is not open with this installation.', {'projects': projects})
            return self.bridges[selected]
        if len(projects) == 1:
            return self.bridges[Path(projects[0]['project'])]
        if not projects:
            raise ToolError('NO_OPEN_PROJECT', 'Open a linked Godot project to connect its editor.', {'projects': []})
        raise ToolError('PROJECT_REQUIRED', 'Several Godot projects are open. Select one with get_context(project="/absolute/path").', {'projects': projects})

    def context(self) -> dict:
        projects = self.projects()
        return {'version': PRODUCT_VERSION, 'engine_version': ENGINE_VERSION, 'protocol': PROTOCOL_VERSION,
                'server_ready': True, 'projects': projects, 'project': None,
                'selection_required': len(projects) > 1,
                'message': 'Select a project with get_context(project="/absolute/path").' if projects else 'Open a linked Godot project; the server is ready.'}
