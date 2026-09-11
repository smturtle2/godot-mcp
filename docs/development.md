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
GODOT_MCP_INTEGRATION=1 uv run pytest -m integration
uv run scripts/verify_install.py
```

The installation check covers initial setup, MCP plugin installation, live editing, stable commands, reinstall reuse, and repair. It uses an isolated installation without changing the user's PATH.

## Runtime design

```text
MCP client → stdio server → authenticated WebSocket → Godot EditorPlugin
                    └── install_plugin → project files and plugin activation
```

The client owns server startup and shutdown. The Python server validates tool arguments and selects a project; the plugin owns live scenes, unsaved state, editor history, and game operations. `install_plugin` and CLI `init` share the transactional installer and work before an editor connection exists.

Source state belongs to `source_store.gd`, compiler snapshots to `source_validation.gd`, and edit/save orchestration to `documents.gd`. Single-file and batch edits share the same revision checks, live state, validation, and undo path.

The shared mutation boundaries have explicit owners:

| Responsibility | Owner |
|---|---|
| Public schemas and complete object variants | `catalog.py` |
| Resource selectors, node ownership and scope validation | `resource_target.gd` |
| Property decoding, type checks and attachment compatibility | `property_edits.gd` |
| Editor buffer observation and its saved revision baseline | `source_store.gd` |
| Snapshot copy/fingerprint exclusions and compiler verdicts | `source_validation.gd` |
| Bounded stdout/stderr byte collection and UTF-8 decoding | `process_output.gd` |
| Import phases, timeout continuation and retained operation state | `import_operations.gd` |
| File before/after images and content guards | `file_journal.gd` |
| Applied effects, failures and pending stages in compound results | `operation_result.gd` |
| Injected input state and capture coordinate conversion | `runtime.gd` |
| Filtered log pagination for editor and runtime | `log_buffer.gd` |

Property plans decode values once and are consumed by their scene or resource owner. Source compilation remains a document operation. Import continuations wait for importer quiescence and acquire the same mutation gate as requests before changing options or registering undo. Pending operations are retained in the current editor session; completed records are evicted when the 32-record limit is reached.

Integration fixtures may instrument the copied plugin to control importer waits, partial writes and native editor buffer changes. Production code does not expose those test commands. Validate both successful results and partial results against their MCP output schemas. Schema tests verify the raw catalog and server boundary; rendering by an external client's schema converter requires a separate client reconnect check.

See [state and recovery](workflows.md) for caller-visible conflict, timeout and retry behavior.

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
