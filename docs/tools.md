# Godot MCP tool reference

Generated from [`TOOL_SPECS`](../src/godot_mcp/catalog.py). MCP `tools/list` publishes the named input schemas; strict server validation remains authoritative.

Document and import mutations return a compact receipt with an `operation_id`. Use `get_operation_result(operation_id)` for the retained operation-time snapshot and current Undo eligibility; never rerun a mutation to retrieve details. Records are bounded to 64 entries and 16 MiB of serialized result bytes.

`install_plugin` can install and enable the project plugin before an editor connection exists. After opening the project, use `get_context` for live editor state.

| Tool | Description |
|---|---|
| `install_plugin` | Install and enable the bundled plugin in an existing Godot project before connecting to the editor. Close the project in Godot first. Creates a rollback backup and registers project discovery. |
| `get_context` | Read project/engine/product/protocol versions, active scene, selection, unsaved documents, pending operation IDs and actual run state. |
| `get_operation_result` | Read the retained detailed result of a document mutation or import without repeating it. Results are operation-time snapshots; current_undo reports current eligibility separately. The editor session retains at most 64 records and 16 MiB of serialized results, evicting completed records first. Expired, unknown, or oversized pending records return explicit errors. |
| `find_assets` | Search filenames, source text or symbols. Returns reusable res:// URIs and one-based source locations. |
| `get_class_info` | Inspect actual engine or project script classes, properties, methods and signals; optionally filter a member. |
| `get_scene` | Inspect live scene nodes, unsaved values, connections, inheritance overrides and actual Control layout. |
| `open_scene` | Open and activate a saved scene in the editor. |
| `create_scene` | Create a scene with a typed root or inherited source. Saves the new file and returns its root reference. |
| `create_nodes` | Create a flat related-node batch. Each node requires name and exactly one source choice: class, instance, or duplicate; parent_key links nodes within the batch. Returns actual names and references. |
| `update_nodes` | Batch node properties, names and reparenting in one scene. Use references in the source scene to edit the original. Container-controlled layout is reported. |
| `delete_nodes` | Delete related nodes with undo; report affected persistent connections and NodePath references. Reject inherited members and overlapping selections. |
| `save_documents` | Save requested documents; Godot scene saves may also persist linked resources. Reports observed extra source saves, partial failures, and the separate undo boundary. |
| `undo_edit` | Undo the latest MCP edit if its editor history has not changed since. Filesystem operations report their separate rollback scope. |
| `get_resource` | Read a resource selected by uri or by node scene/path/property, including nested references, known users and import provenance. Sharing scan covers open scenes and indexed project dependencies. |
| `create_resource` | Create an in-memory resource, optionally attach it or save it. Returns a reusable resource URI. |
| `update_resource` | Change a resource with an explicit local or shared target. Imported shared sources require detaching to an authored resource. |
| `read_script` | Read the current source, including unsaved editor/store changes, with its revision and symbols. Ranges use one-based Unicode columns and exclusive ends. |
| `create_script` | Create and save the source before validation. If attachment fails, the source remains saved. Repair source with edit_script, then retry node script attachment with update_nodes (script property) or shader attachment with update_resource (ShaderMaterial shader property). |
| `edit_script` | Apply a complete source replacement or one or more range edits at an exact revision; changes remain live even when compilation fails. The change selects exactly one replace or edit payload. Save explicitly to persist. |
| `apply_script_changes` | Apply a bounded batch of live source changes; save=true persists the batch afterward. Changes remain live on compile failure, attachments are outside this batch, and game hot reload is not promised. Validation snapshots exclude caches/symlinks and are limited to 512 MiB and 20,000 files. |
| `update_signals` | Connect/disconnect persistent signal handlers with optional binds in one scene. Missing handler code is reported. |
| `get_animation` | Inspect animation tracks/keys or AnimationTree states, transitions, blend connections and parameter values. |
| `edit_animation` | Create or edit an AnimationPlayer animation and typed tracks/keys. Local scope isolates a player's shared library; shared scope is explicit. |
| `edit_animation_graph` | Build state machines or blend trees/spaces with transitions, connections and parameters, as one undoable graph edit. |
| `preview_animation` | Interpolate a pose at a time, capture the real editor viewport, and restore values. Method/audio tracks are not executed. |
| `get_tilemap` | Read TileMapLayer cells and reusable atlas/tile/terrain identifiers. Reads a bounded region or up to limit used cells. |
| `edit_tileset` | Batch atlas, collision and terrain edits on a staged TileSet with one undo. Choose a local node property or shared resource target explicitly. |
| `paint_tiles` | Paint cells, regions, patterns or terrain paths and report all actual changes including auto-connected neighbors. Undo restores prior cells. |
| `inspect_runtime` | Read the actual game's scene tree or node properties with run ID and observation time. |
| `capture_viewport` | Return actual PNG pixels plus viewport/capture coordinates. Headless rendering returns an explicit unsupported error. |
| `wait_for_condition` | Observe scene/node/property/signal conditions until satisfied or a bounded timeout; returns last observation. |
| `get_diagnostics` | Read a fresh snapshot validation of requested sources plus historical editor log entries; unsaved dependencies are included. Snapshot validation excludes caches/symlinks and is limited to 512 MiB and 20,000 files. |
| `sample_performance` | Measure supported Performance monitors over time; include units, sample count and conditions. Unknown metrics are rejected. |
| `run_scene` | Start an editor-launched game and wait for the actual runtime helper handshake. Save/restart are explicit (default false). |
| `stop_game` | Stop the specified run, release injected input, and confirm process termination. |
| `send_input` | Send timestamped key/mouse/touch/action events through Godot input; each event selects exactly one named kind payload. Capture position and relative coordinates use capture pixels. Timeouts retain applied effects; retry failed observation or capture rather than repeating the mutation. |
| `inspect_debugger` | Read suspended DAP stack/scopes/variables; frame handles become stale on continue. GDScript is supported. |
| `set_breakpoints` | Add/remove MCP-owned breakpoints while preserving user breakpoints. replace=true replaces only MCP-owned entries. |
| `debug_control` | Pause, continue, step over or step into GDScript. step_out reports unsupported on Godot 4.7.2. |
| `get_settings` | Read project settings, input mappings and autoloads with property metadata. |
| `get_export_presets` | Read actual preset names/platforms and installed export-template readiness. |
| `import_assets` | Copy local assets or reimport project assets with options. Timeouts retain applied effects and return an operation ID; query the operation rather than repeating the mutation. |
| `move_assets` | Move project files with UID sidecars and reconcile serialized dependencies. Reject unsaved documents and report dynamic references needing review. |
| `update_settings` | Apply project settings/input actions/autoload changes with undo; save project.godot explicitly to persist. |
| `export_build` | Export with a real Godot preset via CLI and verify the output exists. Export success does not imply artifact execution. |