# Development

## Checks

From the repository root:

```sh
uv sync --frozen
uv run pytest
uv run ruff check .
uv run scripts/sync_version.py --check
uv run scripts/generate_tool_docs.py --check
```

Real editor tests require the supported Godot version and an X11 display for viewport capture:

```sh
GODOT_MCP_INTEGRATION=1 uv run pytest tests/test_editor_integration.py
uv run scripts/verify_install.py
```

The installation check covers initial setup, MCP plugin installation, live editing, stable commands, reinstall reuse, and repair. It uses an isolated installation without changing the user's PATH.

## Runtime design

```text
MCP client → stdio server → authenticated WebSocket → Godot EditorPlugin
                    └── install_plugin → project files and plugin activation
```

The client owns server startup and shutdown. The Python server validates tool arguments and selects a project; the plugin owns live scenes, unsaved state, editor history, and game operations. `install_plugin` and CLI `init` share the transactional installer and work before an editor connection exists.

The stable launcher reads `active.json` to select the server environment. Retain its original runtime environment when maintaining installations. Setup must remain unattended and independent of client configuration files or Godot executable discovery.

Save explicitly before running a game. Runtime references expire with their run; debugger references expire on resume. Headless viewport capture and DAP `step_out` are unsupported. Export checks artifact creation, not whether the exported application runs.

## Releases

`src/godot_mcp/version.py` is the version source. After changing versions or tool contracts, regenerate and run the checks above:

```sh
uv run scripts/sync_version.py
uv run scripts/generate_tool_docs.py
uv run scripts/build_release.py --output dist/release
```

Review archive contents and manifest hashes before publishing. Engine or protocol updates also require the integration suite and clean installation check. Update dependencies with `uv lock` when needed. Native validation beyond Linux x86_64 remains pending.
