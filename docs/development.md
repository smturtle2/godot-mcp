# Development

## Setup and checks

Use the locked environment from the repository root:

```bash
uv sync --frozen
uv run pytest
uv run ruff check .
uv run scripts/sync_version.py --check
uv run scripts/generate_tool_docs.py --check
```

The unit and contract suite does not require Godot. Real editor coverage is opt in:

```bash
GODOT_MCP_INTEGRATION=1 uv run pytest tests/test_editor_integration.py
```

That suite requires a supported local Godot editor and an X11 display for game viewport capture. Linux x86_64 is runtime-tested; native validation on macOS, Windows, and Linux ARM64 remains pending. Treat the suite as representative scope validation.

## Setup interfaces

The MCP client starts the registered `connect --home HOME` stdio server. The `install_plugin` setup tool accepts an absolute project directory and uses the server’s configured home to run the transactional plugin installer before an editor connection exists. `godot-mcp init [PROJECT] --home HOME` is the CLI equivalent; when `PROJECT` is omitted it uses the current folder. Do not add executable detection or prompts to these flows.

## Generated files and releases

`src/godot_mcp/version.py` is the version source. Synchronize addon metadata and tool documentation after changes:

```bash
uv run scripts/sync_version.py
uv run scripts/generate_tool_docs.py
uv run scripts/sync_version.py --check
uv run scripts/generate_tool_docs.py --check
```

Build the reproducible source archive and manifest with:

```bash
uv run python scripts/build_release.py --output dist/release
```

Use `--skip-wheel` when only the source archive is needed. Inspect artifact names, sizes, and SHA-256 values before publishing. The public bootstrap fetches the latest stable release; no Godot executable or engine version is selected by the installer.

Run the clean installation smoke check in a temporary directory:

```bash
uv run python scripts/verify_install.py
```

It checks environment setup, global stdio startup, plugin installation through MCP before Godot opens, CLI initialization, project discovery, editor connection, reinstall reuse, and repair. It requires a usable supported Godot runtime, but the installer itself does not locate or prompt for that executable.

## Engine and protocol updates

Review upstream release and API changes before editing integration code. Update `src/godot_mcp/version.py`, adjust dependency constraints in `pyproject.toml` when needed, then run `uv lock` and `uv sync --frozen`. Regenerate addon metadata and tool documentation, run unit and opt-in editor tests, exercise representative setup and editor workflows, and repeat the clean installation check.

Keep debugger limitations explicit: pausing outside a GDScript frame cannot be stepped, and `step_out` is unsupported by the current Godot DAP adapter. Update the MCP client’s registered executable path after an environment update if the installer prints a new path; there is no stable launcher.
