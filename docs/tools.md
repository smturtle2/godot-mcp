Godot MCP v4.7.2_18 · Godot 4.7.2 · Section: tools

# Choosing tools

Choose the action that matches the task. The catalog below comes from the installed server's tool definitions. MCP publishes the complete input schemas alongside those definitions; use them for argument shapes. The `work` section contains examples, `model` explains common concepts, and `recovery` explains failed or incomplete operations.

| Need | Tools and distinction |
|---|---|
| Learn or connect | `get_guide` reads this manual without an editor. `install_plugin` links a closed project. `get_context` discovers projects or inspects live state. |
| Discover project contents | `find_assets` lists or searches files and drafts. `get_scene` inspects live nodes. `get_resource` reads resource properties. `get_class_info` inspects actual class members. |
| Change scenes | `create_scene` creates a saved scene. `create_nodes` builds a related batch; `update_nodes` edits existing nodes; `delete_nodes` removes nodes. `open_scene` changes the editor's active scene. |
| Edit source and bindings | `read_scripts` returns current text and revisions. `apply_script_changes` applies related source edits and optional bindings. `update_signals` changes connections without source edits. |
| Change resources | `create_resource` creates an engine resource. `update_resource` edits an existing local or shared resource. `save_documents` persists authored documents. |
| Continue or recover | `get_operation_result` observes retained work. `resume_script_changes` continues a blocked source bundle. `undo_edit` uses editor history; `restore_assets` restores durable deletion backups. |
| Manage assets | `import_assets` copies/imports local data. `move_assets` reconciles paths. `delete_assets` previews/applies deletion; `purge_deleted_assets` permanently removes recovery backups. |
| Author animation or tiles | Animation read, edit, graph, and preview tools serve different animation tasks. `get_tilemap`, `edit_tileset`, and `paint_tiles` inspect cells, configure tiles, and place them. |
| Run and observe | `run_scene` and `stop_game` control a run. `inspect_runtime` reads live game nodes; `capture_viewport` returns pixels. `send_input` interacts with the game; `wait_for_condition` waits for an observation; `sample_performance` measures a bounded interval. |
| Investigate a problem | `get_logs` reads historical events. `get_diagnostics` explicitly compiles a source snapshot. Debugger inspection, breakpoints, and control work with a suspended GDScript run. |
| Configure and export | Settings tools read/edit project configuration. `get_export_presets` inspects preset/template readiness; `export_build` creates an artifact. |

Successful operations may return an `operation_id` for retained details. Observing that ID does not repeat the original action. A source diagnostic verdict and an editor error log answer different questions; choose according to the problem being investigated.

## Current tool catalog

Argument schemas are published in MCP tools/list.

| Tool | Description |
|---|---|
| `get_guide` | Read the Godot MCP manual. Omit section to get the index; select a section to read its English content. |
| `install_plugin` | Install and enable the bundled plugin in an existing Godot project before connecting to the editor. Close the project in Godot first. Creates a rollback backup and registers project discovery. |
| `get_context` | Read versions, active scene, selection, unsaved documents, pending operations, run state and durable deletion records for restore or purge. Use scope=progress for a compact operation status; set runtime_details=true to request fresh runtime source provenance. |
| `get_operation_result` | Read retained results without repeating work; wait_ms optionally waits for running work. Snapshots preserve operation-time facts; current_undo/current_resume report live eligibility. The editor retains 64 results/16 MiB per session, evicting completed records first. |
| `find_assets` | Search paths, live source text or symbols, including never-saved drafts, or list files, directories and live source drafts. Name, content and symbol modes require a nonempty query and use case-insensitive substring matching; list ignores query. Listing excludes dot paths and symlinks, reuses project bounds and skipped-path reporting, and recursive controls directory traversal (default true). Source matches include their read revision; pagination observes current state. |
| `delete_assets` | Preview or delete assets and their companions. Preview locks the selected mode, reference policy and current revisions; a stale plan must be previewed again. allow_broken reports references that will remain broken. permanent deletion is irreversible; recoverable backups survive editor restarts and can be inspected with Undo/get_operation_result. |
| `purge_deleted_assets` | Preview or permanently purge recoverable asset backups by deletion ID. Preview locks the selected IDs and revisions; a stale plan must be previewed again. Purging invalidates restore for those backups and cannot be undone. |
| `restore_assets` | Restore a recoverable deletion by deletion ID. Optional paths select a subset of backed up entries and expand folders and companion files. The operation reports editor synchronization and can be followed with Undo/get_operation_result. |
| `get_class_info` | Inspect actual engine or project script classes, properties, methods and signals; optionally filter a member. |
| `get_scene` | Inspect live scene nodes, unsaved values, connections, inheritance overrides and actual Control layout. |
| `open_scene` | Open and activate a saved scene in the editor. |
| `create_scene` | Create a scene with a typed root or inherited source. Saves the new file and returns its root reference. |
| `create_nodes` | Create a flat related-node batch. Each node requires name and exactly one source choice: class, instance, or duplicate; parent_key links nodes within the batch. Returns actual names and references. |
| `update_nodes` | Batch node properties, names and reparenting in one scene. Use references in the source scene to edit the original. Container-controlled layout is reported. |
| `delete_nodes` | Delete related nodes with undo; report affected persistent connections and NodePath references. Reject inherited members and overlapping selections. |
| `save_documents` | Persist the listed authored documents. Imported resources are managed by import; use save_as to export an authored copy. A scene save that could save other edited authored documents first returns SAVE_SCOPE_REQUIRED with their paths. Saving and source validation are independent; editor Undo does not restore saved disk files. |
| `undo_edit` | Undo the latest MCP edit if its history and state guards still match. Recoverable asset deletion restores stored files and may return an operation_id while the editor scans; permanent deletion and purged recovery have no Undo. |
| `get_resource` | Read a resource selected by uri or by node scene/path/property, including nested references, known users and import provenance. Sharing scan covers open scenes and indexed project dependencies. |
| `create_resource` | Create an in-memory resource, optionally attach it or save it. Returns a reusable resource URI. |
| `update_resource` | Change a resource with an explicit local or shared target. Imported shared sources require detaching to an authored resource. |
| `read_scripts` | Read one or more current editor sources/drafts, their revisions and symbols. Pass updated paths' base_revisions to apply_script_changes. Ranges use one-based Unicode columns and exclusive ends. Read bases are retained for three-way merge within 256 versions/16 MiB per editor session. |
| `apply_script_changes` | Apply one context patch to live editor sources. Use *** Begin Patch, *** Add File: res://..., *** Update File: res://..., @@ context hunks and *** End Patch; hunk lines use space/-/+. Up to 100 sources; exact context, no whitespace fuzz. Independent concurrent edits merge against retained read bases; conflicts change nothing. One operation coordinates persistence, editor reload, source attachment and signals. Separate snapshot validation runs only when get_diagnostics is requested. By default wait up to 15 seconds for completion; pending work continues automatically and is queried by ID. Reload failures preserve applied and saved source. reload defaults to auto; defer pauses before explicit editor reload with RELOAD_DEFERRED; continue with resume_script_changes. |
| `resume_script_changes` | Continue a blocked source bundle from its unfinished phase without replaying its patch, completed saves or successful bindings. Accepting changed source revisions repeats only the required source saves and reloads. After repairing source, provide every original source's current read revision. Target changes still cause conflicts. Continuations are bounded to 32 running/blocked bundles per editor session. reload defaults to auto; auto continues a previously deferred explicit reload. |
| `update_signals` | Connect/disconnect persistent signal handlers with optional binds in one scene. Missing handler code is reported. |
| `get_animation` | Inspect animation tracks/keys or AnimationTree states, transitions, blend connections and parameter values. |
| `edit_animation` | Create or edit an AnimationPlayer animation and typed tracks/keys. Local scope isolates a player's shared library; shared scope is explicit. |
| `edit_animation_graph` | Build state machines or blend trees/spaces with transitions, connections and parameters, as one undoable graph edit. |
| `preview_animation` | Interpolate a pose at a time, capture the real editor viewport, and restore values. Method/audio tracks are not executed. |
| `get_tilemap` | Read TileMapLayer cells and reusable atlas/tile/terrain identifiers. Reads a bounded region or up to limit used cells. |
| `edit_tileset` | Batch atlas, collision and terrain edits on a staged TileSet with one undo. Choose a local node property or shared resource target explicitly. |
| `paint_tiles` | Paint cells, regions, patterns or terrain paths and report all actual changes including auto-connected neighbors. Undo restores prior cells. |
| `inspect_runtime` | Read the actual game's scene tree or node properties with run ID and observation time. |
| `capture_viewport` | Return actual PNG pixels plus viewport/capture coordinates. viewport.kind may select game, editor_2d, editor_3d, or an editor_window; detached windows are selected with window_id from get_context.editor_windows. window_id and scene assert the selected window or active scene and do not open it. framing defaults to current; scene and selection frame editor content, while explicit bounds require non-current framing. rect is a pixel crop; max_width and max_height explicitly downscale, and omitted limits preserve original pixels. Window captures return client area. Headless rendering returns an explicit unsupported error. |
| `wait_for_condition` | Observe scene/node/property/signal conditions until satisfied or a bounded timeout; returns last observation. |
| `get_diagnostics` | Explicitly validate a captured snapshot of sources and unsaved dependencies; no historical logs or guarantee that the live project remains unchanged. Unrelated live edits do not discard captured results. Returns an operation_id immediately when validation exceeds wait_ms (default 1500); use get_operation_result to wait without repeating work. Omitted uris selects authored project sources, excluding this plugin. Counts describe only complete snapshot coverage; pending/unavailable is not error-free. Snapshots exclude dot caches/symlinks and are limited to 512 MiB/20,000 files. |
| `get_logs` | Read historical editor or selected-run log entries with cursor pagination. Log occurrence or silence does not establish whether current source is valid or a runtime problem is resolved. |
| `sample_performance` | Measure supported Performance monitors over time; include units, sample count and conditions. Unknown metrics are rejected. |
| `run_scene` | Start a game with a recorded startup source snapshot and runtime handshake. save_uris explicitly lists documents to persist first; other unsaved documents block startup. Optional revisions guard the expected sources. Startup file evidence does not prove changed behavior; use runtime observations. |
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
