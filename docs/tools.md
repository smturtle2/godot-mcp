# Godot MCP tool reference

Generated from [`TOOL_SPECS`](../src/godot_mcp/catalog.py). The canonical JSON input schemas are served by MCP `tools/list`; this page keeps the discoverable catalog compact.

`install_plugin` can install and enable the project plugin before an editor connection exists. After opening the project, use `get_context` for live editor state.

| Tool | Description |
|---|---|
| `install_plugin` | Install and enable the bundled plugin in an existing Godot project before connecting to the editor. Close the project in Godot first. Creates a rollback backup and registers project discovery. |
| `get_context` | Read project/engine/product/protocol versions, active scene, selection, unsaved documents and actual run state. |
| `find_assets` | Search filenames, source text or symbols. Returns reusable res:// URIs and one-based source locations. |
| `get_class_info` | Inspect actual engine or project script classes, properties, methods and signals; optionally filter a member. |
| `get_scene` | Inspect live scene nodes, unsaved values, connections, inheritance overrides and actual Control layout. |
| `open_scene` | Open and activate a saved scene in the editor. |
| `create_scene` | Create a scene with a typed root or inherited source. Saves the new file and returns its root reference. |
| `create_nodes` | Create a flat related-node batch using optional parent_key links, scene instances or duplicates in one undoable edit. Returns actual names and references. |
| `update_nodes` | Batch node properties, names and reparenting in one scene. Use references in the source scene to edit the original. Container-controlled layout is reported. |
| `delete_nodes` | Delete related nodes with undo; report affected persistent connections and NodePath references. Reject inherited members and overlapping selections. |
| `save_documents` | Save requested documents; Godot scene saves may also persist linked resources. Reports observed extra source saves, partial failures, and the separate undo boundary. |
| `undo_edit` | Undo the latest MCP edit if its editor history has not changed since. Filesystem operations report their separate rollback scope. |
| `get_resource` | Read resource properties, nested references, known users and import provenance. Sharing scan covers open scenes and indexed project dependencies. |
| `create_resource` | Create an in-memory resource, optionally attach it or save it. Returns a reusable resource URI. |
| `update_resource` | Change a resource with explicit node-local or shared scope. Imported shared sources require detaching to an authored resource. |
| `read_script` | Read the current source, including unsaved editor/store changes, with its revision and symbols. Ranges use one-based Unicode columns and exclusive ends. |
| `create_script` | Create and save the source before validation; compilation or attachment failures leave the file saved and should be retried with edit_script. |
| `edit_script` | Apply a live source edit at an exact revision; changes remain live even when compilation fails, and game hot reload is not promised. Save explicitly to persist. |
| `apply_script_changes` | Apply a bounded batch of live source changes; save=true persists the batch afterward. Changes remain live on compile failure, attachments are outside this batch, and game hot reload is not promised. Validation snapshots exclude caches/symlinks and are limited to 512 MiB and 20,000 files. |
| `update_signals` | Connect/disconnect persistent signal handlers with optional binds in one scene. Missing handler code is reported. |
| `get_animation` | Inspect animation tracks/keys or AnimationTree states, transitions, blend connections and parameter values. |
| `edit_animation` | Create or edit an AnimationPlayer animation and typed tracks/keys. Node scope isolates a player's shared library; shared scope is explicit. |
| `edit_animation_graph` | Build state machines or blend trees/spaces with transitions, connections and parameters, as one undoable graph edit. |
| `preview_animation` | Interpolate a pose at a time, capture the real editor viewport, and restore values. Method/audio tracks are not executed. |
| `get_tilemap` | Read TileMapLayer cells and reusable atlas/tile/terrain identifiers. Reads a bounded region or up to limit used cells. |
| `edit_tileset` | Author atlas tiles, collision polygons and terrain/peering rules on a staged TileSet, then commit with undo. |
| `paint_tiles` | Paint cells, regions, patterns or terrain paths and report all actual changes including auto-connected neighbors. Undo restores prior cells. |
| `inspect_runtime` | Read the actual game's scene tree or node properties with run ID and observation time. |
| `capture_viewport` | Return actual PNG pixels plus viewport/capture coordinates. Headless rendering returns an explicit unsupported error. |
| `wait_for_condition` | Observe scene/node/property/signal conditions until satisfied or a bounded timeout; returns last observation. |
| `get_diagnostics` | Read a fresh snapshot validation of requested sources plus historical editor log entries; unsaved dependencies are included. Snapshot validation excludes caches/symlinks and is limited to 512 MiB and 20,000 files. |
| `sample_performance` | Measure supported Performance monitors over time; include units, sample count and conditions. Unknown metrics are rejected. |
| `run_scene` | Start an editor-launched game and wait for the actual runtime helper handshake. Save/restart are explicit (default false). |
| `stop_game` | Stop the specified run, release injected input, and confirm process termination. |
| `send_input` | Send timestamped key/mouse/touch/action events through Godot input. Optionally observe a condition and capture afterward. Capture URI enables conversion from image coordinates. |
| `inspect_debugger` | Read suspended DAP stack/scopes/variables; frame handles become stale on continue. GDScript is supported. |
| `set_breakpoints` | Add/remove MCP-owned breakpoints while preserving user breakpoints. replace=true replaces only MCP-owned entries. |
| `debug_control` | Pause, continue, step over or step into GDScript. step_out reports unsupported on Godot 4.7.2. |
| `get_settings` | Read project settings, input mappings and autoloads with property metadata. |
| `get_export_presets` | Read actual preset names/platforms and installed export-template readiness. |
| `import_assets` | Copy local assets or reimport project assets with options, wait for Godot import, and report resource references and persistence risks. |
| `move_assets` | Move project files with UID sidecars and reconcile serialized dependencies. Reject unsaved documents and report dynamic references needing review. |
| `update_settings` | Apply project settings/input actions/autoload changes with undo; save project.godot explicitly to persist. |
| `export_build` | Export with a real Godot preset via CLI and verify the output exists. Export success does not imply artifact execution. |