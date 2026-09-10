# Architecture

`godot-mcp` has two cooperating processes. The Python MCP server speaks MCP over stdio to the client. The Godot addon runs inside the editor and owns live project state, unsaved documents, editor history, and the running game. The server reaches the addon through an authenticated loopback bridge.

```text
MCP client
    │ stdio
    ▼
Python server (server.py)
    ├── catalog.py       tool names, descriptions, JSON Schema 2020-12
    ├── bridge.py        loopback transport, validation, request/response errors
    ├── debugger.py      DAP connection and breakpoint/step operations
    ├── installer.py     versioned environment, addon install, client registration
    └── client_config.py JSON/TOML client configuration updates
             │ authenticated loopback
             ▼
Godot EditorPlugin (addon/plugin.gd)
    ├── scenes.gd / documents.gd / resources.gd
    ├── animations.gd / tiles.gd / assets.gd
    ├── debugger.gd / runtime.gd / runtime_tools.gd
    └── codec.gd / log_buffer.gd / version.gd
             │
             ▼
       Editor, project files, and game runtime
```

## Python modules

| Module | Responsibility |
| --- | --- |
| `server.py` | Creates the official MCP SDK server, validates tool arguments, dispatches calls, and converts captured PNG data to MCP image content. |
| `catalog.py` | Defines the 42 executable tool specifications and their input schemas. `docs/tools.md` is generated from this catalog. |
| `bridge.py` | Validates project paths and values, manages the authenticated editor connection, and exposes tool calls and structured errors. |
| `debugger.py` / `dap.py` | Implements debugger requests over Godot's DAP connection, including MCP-owned breakpoints and GDScript stepping. |
| `installer.py` | Prepares a version-isolated installation, copies the addon, updates client registration, and records rollback state. |
| `client_config.py` | Performs atomic JSON/TOML MCP configuration updates while preserving unrelated settings. |
| `cli.py` | Provides `version`, `serve`, `check`, and `install` commands. |
| `version.py` | Single source for product, engine, and protocol versions. |

## Godot addon modules

The addon entry point is `plugin.gd`. Feature modules are kept by domain: scene editing in `scenes.gd`, document persistence in `documents.gd`, resources in `resources.gd`, animation in `animations.gd`, TileMap/TileSet work in `tiles.gd`, and asset operations in `assets.gd`. `runtime.gd` and `runtime_tools.gd` exchange observations and input with the actual game. `debugger.gd` connects editor debugger events; `codec.gd` serializes typed Godot values; `log_buffer.gd` buffers diagnostics safely across callbacks. `version.gd` is generated from the Python version source.

The editor is authoritative for live state. Tools read open scenes, unsaved script buffers, resources, and editor selections through Godot APIs. Save operations are explicit. Mutations use editor undo history where supported and return references, revisions, or run IDs that subsequent calls can validate.

## Request lifecycle

1. `server.py` receives a named MCP tool call and validates its JSON Schema.
2. `bridge.py` checks project-local paths and values, then sends a bounded request to the matching addon handler.
3. The addon performs the operation on the editor's main thread, stages changes, and returns structured state or a typed error.
4. The server returns JSON content and, for viewport captures, PNG image content.
5. Runtime observations are tied to a current `run_id`; debugger frame handles become stale after continue or stepping.

The loopback endpoint is authenticated and version checked. A mismatched project, product, engine, or protocol produces an explicit error. Timeouts are not automatic permission to retry a mutation: inspect state first.

## Boundaries and known behavior

- `capture_viewport` returns actual rendered pixels and reports headless rendering as unsupported.
- `debug_control` supports pause, continue, step over, and step into. Paused execution outside a script frame cannot be stepped; `step_out` is unsupported on Godot 4.7.2.
- Imported shared resources and dynamic asset references carry persistence risks; tools report these for review instead of silently rewriting them.
- `export_build` verifies that an export artifact exists. Artifact execution is a separate check.

## Global process and project discovery

The normal deployment is one client-started stdio process. `connect --home` creates a discovery-backed server; it does not start a background HTTP daemon. `EditorDirectory` reads registrations under `HOME/editors`, validates the endpoint project, product version, epoch, and live editor PID, and filters stale or closed entries. With one valid project selection is automatic. With multiple projects, `get_context` returns the choices and a tool call may include an absolute `project` selector. A successful selection is remembered for the MCP connection; a closed selected project returns an error rather than selecting another project silently.

`serve --project` remains a compatibility path for a client that already supplies one project. In that mode the bridge is fixed to that project and rejects a different selector.

The installer’s global transaction updates the active executable, client registrations, and every project recorded under the same home. Its rollback journal contains child project transactions and snapshots of global configuration, so rollback restores the full installation scope.
