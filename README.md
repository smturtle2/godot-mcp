# godot-mcp

<p align="center">
  <img src="docs/assets/hero-blueprint.png" alt="Godot MCP scene blueprint" width="900">
</p>

<p align="center"><strong>Inspect, edit, run, and debug Godot projects through MCP.</strong><br>
Give an MCP client a live, version-checked bridge to the Godot editor and game runtime.</p>

<p align="center">
  <a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/Godot-4.7.2-478cbf?logo=godotengine&logoColor=white" alt="Godot 4.7.2"></a>
  <a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/MCP-2026--07--28-5b5bd6" alt="MCP 2026-07-28"></a>
  <a href="https://www.python.org/downloads/release/python-3130/"><img src="https://img.shields.io/badge/Python-3.13-3776ab?logo=python&logoColor=white" alt="Python 3.13"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-EUPL--1.2-green" alt="EUPL-1.2 license"></a>
</p>

## What it does

`godot-mcp` connects an MCP client to a Godot project over an authenticated loopback bridge. Its 42 tools cover the editor, authored project files, runtime observation, input, debugging, animation, TileMap/TileSet work, settings, and export.

The bridge reports project, engine, product, and protocol versions through `get_context`. Mutating operations are staged through the editor where possible, with explicit save and undo behavior. Runtime operations return run identifiers and observations so an agent can verify what actually happened.

Read the [tool reference](docs/tools.md) for the complete catalog and JSON schemas. The [architecture guide](docs/architecture.md) maps the server, bridge, editor plugin, and tool catalog.

## Install once, connect your projects

Requires **Godot 4.7.2**. The installer prepares uv, Python 3.13, and a versioned server environment for your user account.

```sh
curl -fsSL https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.ps1 | iex
```

Choose your MCP app configuration during installation. You can link a Godot project now or later. Existing settings are preserved. Use the installed executable printed at the end to link another project:

```sh
"/absolute/installed/godot-mcp" install --plugin-only --yes --project /path/to/project
```

**Who starts what?** You open your AI app (for example, Codex or Cursor); it starts the registered MCP server automatically. Opening a linked Godot project enables its plugin and makes it discoverable. Either app can be opened first. No per-project MCP registration or manual server startup is needed.

With several projects open, `get_context` lists them. Select one with its `project` argument; the server remembers that choice for the session. Each tool also accepts an explicit project path.

Re-run the installer to update the common server, saved MCP registrations, and linked plugins. Close linked Godot editors first. Add `--repair` for a fresh environment. See [installation, verification, and rollback](docs/installation.md).

<details>
<summary>Install from source</summary>

```bash
git clone https://github.com/smturtle2/godot-mcp.git
cd godot-mcp
uv sync --frozen
uv run godot-mcp install
```

Open a linked project, then verify its connection:

```bash
uv run godot-mcp check --project /path/to/project
```

</details>

## Example workflows

An MCP client can use the tools as a verified workflow rather than editing files blindly:

```text
get_context → find_assets → open_scene → get_scene
create_nodes/update_nodes → save_documents → run_scene
inspect_runtime → send_input → capture_viewport → stop_game
```

Typical tasks include:

- inspect a scene and locate a node or script symbol;
- create or update a scene subtree, then save only the requested documents;
- run the game, send input, wait for a condition, and capture the real viewport;
- inspect diagnostics or debugger state, set breakpoints, and step through GDScript;
- author animation graphs, TileSet data, terrain paths, project settings, or export builds.

## Version matrix

| Component | Version |
| --- | --- |
| Godot engine | 4.7.2 |
| Product tag | `v4.7.2_1` |
| MCP protocol | `2026-07-28` |
| Python | 3.13 |
| License | EUPL-1.2 |

The editor plugin and Python server must use compatible product and protocol versions. An incompatible connection fails with an explicit version mismatch.

## Current limitations

- The integration is pinned to Godot 4.7.2; other engine versions require validation before use.
- Linux x86_64 is runtime-tested. Source packages and installers cover macOS, Windows, and Linux ARM64; native validation on those platforms remains outstanding.
- Headless viewport capture returns an explicit unsupported result.
- `debug_control` supports pause, continue, step over, and step into; `step_out` is unsupported on Godot 4.7.2.
- Dynamic asset references reported by move/import operations require manual review.
- Export success verifies the generated artifact exists; it does not verify that the exported artifact runs.

## Development

```bash
uv sync --frozen
uv run pytest
uv run ruff check .
```

See [development](docs/development.md) for the repository workflow and validation expectations. Contributions should preserve explicit version checks, truthful runtime observations, and safe save/undo boundaries.

## License

This project is licensed under the [EUPL-1.2](LICENSE).
