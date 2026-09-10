# Architecture

`godot-mcp` has a client-started Python MCP server and a Godot editor plugin. The MCP client launches the server over stdio. The server owns installation and discovery; the editor owns live project state, unsaved documents, editor history, and the running game. Server-to-editor calls use an authenticated local WebSocket bridge.

```text
MCP client ──stdio──> Python server
                       ├─ install_plugin ──> project files and plugin activation
                       └─ editor tools ──authenticated WebSocket──> Godot EditorPlugin
                                                                  └─ editor and game
```

## Server and setup

`server.py` validates tool schemas, dispatches calls, and remembers a selected project for the MCP connection. The 42 editor/runtime tools are defined in `catalog.py`; `install_plugin` is the setup entry point and accepts an absolute project directory. It uses the server’s configured `--home` and the same transactional project installer as `init`, so it can install and enable the plugin before an editor connection exists.

`installer.py` owns the versioned server environment, project addon/link records, active executable, and project index. `cli.py` exposes `connect`, `init`, `install`, `serve`, `check`, and `version`. `discovery.py` filters registered editors by project, endpoint, product/version compatibility, epoch, and live PID. `bridge.py` validates project values and exchanges bounded requests with the addon. `debugger.py` and `dap.py` handle editor debugger operations.

Client registration and process launch are outside the installer. The client starts the generic `godot-mcp connect --home HOME` stdio command. Godot is opened separately and publishes its endpoint when the project plugin is enabled. There is no stable launcher; an environment update may require the client’s registered executable path to be replaced.

## Editor authority and request flow

1. The client sends a tool call over stdio.
2. The server validates the schema and resolves the optional absolute project selector.
3. The bridge sends the request to the matching editor plugin.
4. The addon performs the operation on Godot’s main thread and returns structured state or an error.
5. The server returns JSON and, for captures, PNG image content.

The editor is authoritative for live scenes, unsaved scripts, resources, selections, and undo history. Save operations are explicit. Runtime observations use current run IDs; debugger frames and variable references expire when execution resumes.

## Discovery behavior

With one open linked project, selection is automatic. With several, `get_context` lists projects and a call can provide an absolute `project` path. A successful selection is remembered for the connection. A closed, stale, or incompatible selected project returns an error rather than silently selecting another.

## Known limits

- The current supported engine is Godot 4.7.2; compatibility is enforced at connection time.
- Headless viewport capture is unsupported.
- Pausing outside a GDScript frame cannot be stepped; `step_out` is unsupported by the current DAP adapter.
- Imported shared resources and dynamic asset references may require manual review.
- Export verifies that an artifact exists; it does not verify that the artifact runs.
