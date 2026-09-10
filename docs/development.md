# Development and upgrades

## Local setup

Use Python 3.13, Godot 4.7.2, and `uv`:

```bash
uv sync --frozen
```

Run the normal checks from the repository root:

```bash
uv run pytest
uv run scripts/sync_version.py --check
uv run scripts/generate_tool_docs.py --check
uv run python scripts/build_release.py --skip-wheel --output dist/release
```

The release command writes a reproducible source archive and manifest. Omit `--skip-wheel` when `uv` should build the wheel as well.

## Test layers

The unit and contract suite runs without Godot:

```bash
uv run pytest
```

The editor integration suite is opt in and uses a real local Godot editor:

```bash
GODOT_MCP_INTEGRATION=1 uv run pytest tests/test_editor_integration.py
```

Use a local Godot 4.7.2 executable. The integration fixture starts an editor and requires a usable X11 display when exercising game viewport capture; set `GODOT` when `godot` is not on `PATH`. The suite covers representative authoring, resources, animation, TileMap, runtime, input, debugger, diagnostics, and export paths. It is a scope check for the implemented integration, not an exhaustive compatibility claim.

## Generated and versioned files

`src/godot_mcp/version.py` is the version source. `scripts/sync_version.py` propagates its engine, product, and protocol values to `src/godot_mcp/addon/version.gd` and `plugin.cfg`. `docs/tools.md` is generated from `godot_mcp.catalog.TOOL_SPECS`.

After changing either source, run:

```bash
uv run scripts/sync_version.py
uv run scripts/generate_tool_docs.py
uv run scripts/sync_version.py --check
uv run scripts/generate_tool_docs.py --check
uv run pytest
```

## Updating Godot or MCP

Start with the official Godot [release archive](https://godotengine.org/download/archive/) and the target version's [release notes and changelog](https://godotengine.org/changelog/). For MCP protocol changes, read the official [MCP specification and announcements](https://modelcontextprotocol.io/specification/latest) and the [MCP blog](https://blog.modelcontextprotocol.io/). Record the API changes that affect editor classes, debugger/DAP behavior, rendering, input, or the MCP SDK before editing code.

1. Update `src/godot_mcp/version.py` with the new engine/product/protocol values.
2. Update `pyproject.toml` dependency pins or Python constraints when the SDK or runtime requires it.
3. Run `uv lock` and then `uv sync --frozen` to validate the locked environment.
4. Run `uv run scripts/sync_version.py` and `uv run scripts/generate_tool_docs.py`.
5. Map each changed API to its module in [architecture](architecture.md), then run unit/contract tests and the real editor integration suite.
6. Exercise all 42 tools through representative workflows, including editor edits, save/undo, runtime input/capture, debugger, and export. Record failures by scope; do not infer support for untested platforms or engine versions.
7. Run the synchronization checks, full test suite, and release build. Confirm the source tag and manifest use the product version (current baseline: `v4.7.2_3`).

Known debugger behavior must remain explicit: pausing outside a script frame cannot be stepped, and this target does not implement `step_out`. Preserve user breakpoints when changing MCP-owned breakpoints.

## Release QA and publishing

Before publishing, use a clean environment to validate installation, editor connection, the 42-tool catalog, and representative runtime operations. Inspect the generated manifest, SHA-256 values, and source archive contents. Publish only after QA passes:

```bash
gh release create v4.7.2_3 dist/release/* --title "godot-mcp v4.7.2_3" --generate-notes
```

Update existing installations only after the new release is available and its checks pass. Keep the prior installation record for rollback. The release process is intentionally separate from source changes; do not publish from an unreviewed working tree.
