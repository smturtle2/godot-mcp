Godot MCP v4.7.2_20 · Godot 4.7.2 · Section: tools

# Tool choices

The index below lists each tool's role. Read one tool's full usage, argument schema, and example when needed:

```json
{"section":"tools","tool":"create_nodes"}
```

Use `work` for task workflows and `model` for editor, resource, and runtime concepts. `create_project` prepares an empty directory through editor connection; its optional environment passes only the supported display/session variables. `install_plugin` links an existing closed project.

For unfinished work, query its `operation_id` with `get_operation_result`; use `resume_script_changes` only for a blocked source bundle. `get_logs` reads historical editor or selected-run history, including retained runtime entries while paused or stopped; `get_diagnostics` explicitly validates a source snapshot. Saving, validation, and runtime behavior are separate facts, summarized in mutation receipts whose state summary includes only evidenced stages.

## Current tool catalog

Read one tool with get_guide({"section":"tools","tool":"create_nodes"}).
Argument schemas are also published in MCP tools/list.

| Tool | Description |
|---|---|
| `get_guide` | Read the manual index, a section, or one tool's usage and schema (section=tools, tool=name). |
| `create_project` | Create an empty project, install the plugin, open Godot and connect. |
| `install_plugin` | Install and enable the bundled plugin in an existing Godot project before connecting to the editor. |
| `get_context` | Read connected projects and editor state. |
| `get_operation_result` | Read retained operation results; wait_ms waits without repeating work. |
| `find_assets` | Search names, source text or symbols with query; mode=list lists files, folders and drafts without a query. |
| `delete_assets` | Preview then delete files/folders and companions. |
| `purge_deleted_assets` | Preview then permanently purge deletion backups. |
| `restore_assets` | Restore a recoverable deletion or selected paths, including companions; returns actual restored files and synchronization state. |
| `get_class_info` | Inspect actual engine or project script classes, properties, methods and signals; optionally filter a member. |
| `get_scene` | Inspect live scene nodes, unsaved values, connections, inheritance overrides and actual Control layout. |
| `open_scene` | Open and activate a saved scene in the editor. |
| `create_scene` | Create a scene with a typed root or inherited source. |
| `create_nodes` | Create a flat related-node batch. |
| `update_nodes` | Batch node properties, names and reparenting in one scene. |
| `delete_nodes` | Delete related nodes with undo; report affected persistent connections and NodePath references. |
| `save_documents` | Save listed authored documents; extra save scope must be explicit. |
| `undo_edit` | Undo the latest MCP edit if its history and state guards still match. |
| `get_resource` | Read a resource selected by uri or by node scene/path/property, including nested references, known users and import provenance. |
| `create_resource` | Create an in-memory resource, optionally attach it or save it. |
| `update_resource` | Change a resource with an explicit local or shared target. |
| `read_scripts` | Read live sources/drafts and revisions for subsequent patches. |
| `apply_script_changes` | Apply a context patch with read revisions; optionally save and bind sources. |
| `resume_script_changes` | Resume a blocked source bundle without replaying completed work. |
| `update_signals` | Connect/disconnect persistent signal handlers with optional binds in one scene. |
| `get_animation` | Inspect animation tracks/keys or AnimationTree states, transitions, blend connections and parameter values. |
| `edit_animation` | Create or edit an AnimationPlayer animation and typed tracks/keys. |
| `edit_animation_graph` | Build state machines or blend trees/spaces with transitions, connections and parameters, as one undoable graph edit. |
| `preview_animation` | Interpolate a pose at a time, capture the real editor viewport, and restore values. |
| `get_tilemap` | Read TileMapLayer cells and reusable atlas/tile/terrain identifiers. |
| `edit_tileset` | Batch atlas, collision and terrain edits on a staged TileSet with one undo. |
| `paint_tiles` | Paint cells, regions, patterns or terrain paths and report all actual changes including auto-connected neighbors. |
| `inspect_runtime` | Read the actual game's scene tree or node properties with run ID and observation time. |
| `capture_viewport` | Capture game/editor pixels with scene and coordinate metadata. |
| `wait_for_condition` | Observe scene/node/property/signal conditions until satisfied or a bounded timeout; returns last observation. |
| `get_diagnostics` | Validate a source snapshot on request; waits up to 15s by default. |
| `get_logs` | Read historical editor or selected-run log entries with cursor pagination. |
| `sample_performance` | Measure supported Performance monitors over time; include units, sample count and conditions. |
| `run_scene` | Start a game and confirm its handshake. |
| `stop_game` | Stop the specified run, release injected input, and confirm process termination. |
| `send_input` | Inject scheduled inputs; optionally observe properties before/after, wait for a condition and capture. |
| `inspect_debugger` | Read suspended DAP stack/scopes/variables; frame handles become stale on continue. |
| `set_breakpoints` | Add/remove MCP-owned breakpoints while preserving user breakpoints. |
| `debug_control` | Pause, continue, step over or step into GDScript. |
| `get_settings` | Read project settings, input mappings and autoloads with property metadata. |
| `get_export_presets` | Read actual preset names/platforms and installed export-template readiness. |
| `import_assets` | Copy local assets or reimport project assets with options. |
| `move_assets` | Move project files with UID sidecars and reconcile serialized dependencies. |
| `update_settings` | Apply project settings/input actions/autoload changes with undo; save project.godot explicitly to persist. |
| `export_build` | Export with a real Godot preset via CLI and verify the output exists. |
