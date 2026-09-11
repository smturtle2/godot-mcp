# State and recovery

## Source workflow

Read current editor sources or drafts with `read_scripts`:

```json
{"documents":[{"uri":"res://main.gd"},{"uri":"res://ui.gd","symbol":"build"}]}
```

The response contains `documents`, `base_revisions`, and `editor_epoch`. A document includes its current `source` and `revision`; an optional `range` uses one-based Unicode columns with an exclusive end. Read bases are retained for conservative three-way merges within the editor session.

Apply all source edits with one `apply_script_changes` patch string. The patch uses this format:

```text
*** Begin Patch
*** Add File: res://new.gd
+extends Node
+
+func run() -> void:
+    pass
*** Update File: res://main.gd
@@
 extends Node
-old_call()
+new_call()
*** End Patch
```

Use `*** Begin Patch`, `*** Add File: res://...` or `*** Update File: res://...`, `@@` context hunks, space/`-`/`+` hunk prefixes, and `*** End Patch`. Updated URIs require their returned values from `base_revisions`; an all-new patch may omit the map. Context is exact and has no whitespace fuzz. Retained bases permit a non-overlapping concurrent edit to merge. Overlapping or ambiguous edits are conflicts and make no source change. `preview: true` returns the guarded text plan and save scope without applying or validating it.

`save` defaults to `false` for both Add and Update, leaving live editor changes as drafts. `save: true` persists sources before validation and saves binding owners after successful binding work. Saved source remains on disk if a later validation phase fails. Source changes already applied remain available for repair after a compile or binding failure. `reload` defaults to `auto`; `reload:"defer"` saves as requested and pauses before explicit editor reload, returning resumable `RELOAD_DEFERRED`. Godot may auto-reload independently.

One operation coordinates these phases, in order: `source`, `save_sources`, `validation`, `editor_reload`, `bindings`, and `save_bindings`. A `pending` response includes `operation_id`; call `get_operation_result` with that ID (and optional `wait_ms`) to wait for the same work without replaying it. The operation result reports per-document state, validation and save effects, failures with phase and recovery details, pending work, and Undo information.

`resume_script_changes` continues blocked or unfinished phases without replaying the patch or successful bindings. It preserves completed bindings. After repairing text, provide a current read revision for every original source in `revisions`; accepting repaired text without all original source revisions is rejected. Changes made to the targets while the operation was blocked still cause conflicts.

Source changes retain one Undo action plus binding steps in newest-first order. Disk files are preserved. Saving a scene can include linked edited sources; if the scope is incomplete, the operation fails with `SAVE_SCOPE_REQUIRED` and reports the additional URIs to pass explicitly to `save_documents`.

Script-only saves do not reopen the current scene. `save_documents` retains its latest save receipt in `.godot-mcp/last-save.json`, exposed as `get_context.last_save` after an editor restart. An interrupted native save has an unknown outcome until its actual disk contents are inspected; connection loss never automatically replays a mutation. Deferred explicit reloads are a mitigation, not a guarantee against crashes in engine or tool-script code.

## Scene access and editor errors

`open_scene` reports the requested and actual active scene, with `opened` and `active` facts. Scene objects are reacquired after activation. Editing or undoing changes in another scene activates its owner first, then restores the previous scene and selection if the user has not navigated elsewhere.

Mutation responses retain their actual effects and attach compact `editor_events` when editor errors or warnings occur during that request. Events include a cursor and a `get_logs` recovery call. Temporal association does not prove that the request caused an error; `get_diagnostics` instead checks current source validity.

## Resource targets

A resource selector is exactly one of these forms:

```json
{"uri":"res://material.tres"}
```

```json
{"node":{"scene":"res://main.tscn","path":"Sprite","property":"material"}}
```

For mutation tools that require scope, use a local node property or shared resource:

```json
{"target":{"local":{"scene":"res://main.tscn","path":"Sprite","property":"material"}},"set":{"albedo":{"$type":"Color","r":1,"g":0.5,"b":0,"a":1}}}
```

```json
{"target":{"shared":{"uri":"res://material.tres"}},"set":{"albedo":{"$type":"Color","r":1,"g":0.5,"b":0,"a":1}}}
```

Read users and import provenance before choosing shared scope. Imported shared sources require detaching to an authored resource before mutation.

## Attachments and connections

Patch attachments are typed. A script attaches a source URI to a node; a shader attaches a source URI to an explicitly scoped ShaderMaterial target:

```json
{"attachments":[{"script":{"uri":"res://player.gd","node":{"scene":"res://main.tscn","path":"Player"}}},{"shader":{"uri":"res://toon.gdshader","target":{"local":{"scene":"res://main.tscn","path":"Player","property":"material"}}}}],"connections":{"connect":[],"disconnect":[]}}
```

`connections.connect` and `connections.disconnect` are arrays of signal records (`from`, `signal`, `to`, `method`, and optional `binds`). Binding and connection work is reported separately from source validation and follows the operation phases.

## Runtime input

Without `capture_uri`, input `position` and `relative` use viewport coordinates. With a capture URI, both use capture image pixels. Positions include crop-origin and resize conversion; relative movement applies only the scale. Mouse button state persists across events and calls, including explicit release and `release_after`; wheel input is momentary.

`send_input` can apply events before its condition wait or capture fails. The result retains `processed`, `held_inputs`, stage results, and `failures`, with `status="partial"` and `complete=false`; retry the failed observation or capture rather than replaying the input sequence. A standalone `wait_for_condition` timeout remains an observation with `timed_out=true`.

## Named mutation inputs

Animation tracks, TileSet changes, input events, conditions, and node creation use one named property for each choice. Examples:

```json
{"event":{"action":{"action":"ui_accept","pressed":true}}}
```

```json
{"property":{"node":{"run_id":"<run_id>","path":"/root/Main"},"property":"visible","value":true,"operator":"eq"}}
```

```json
{"parent":{"scene":"res://main.tscn","path":"."},"nodes":[{"name":"Sprite","source":{"class":"Sprite2D"}}]}
```

Node creation sources are exactly one of `class`, `instance`, or `duplicate`. TileSet and animation resource scope is explicit where the tool schema provides `local` or `shared`.

## Asset imports

`import_assets` creates an operation before writing or reimporting files. A timeout returns the same `operation_id`, applied `files_written` and `options_changed`, the pending phase, and `undo_state="pending"`; Godot may continue importing. Query that operation with `get_operation_result` instead of submitting the same paths again. Once importing settles, the operation records final changes and exposes an `edit_id` only when `undo_state="available"`. External changes during a pending import stop continuation with `IMPORT_CONFLICT`, preserve the file, and make Undo unavailable.

`get_context` reports pending source, diagnostic, and import jobs, along with project/editor/runtime state. Use `scope:"progress"` for compact progress and `runtime_details:true` when fresh source provenance is needed. Routine context, capture, input, and runtime observations omit source provenance unless requested. Import executions are bounded per editor session; result snapshots share the operation retention limits. Editor windows, including detached windows, are listed in `editor_windows` for capture selection.

When the editor is busy, the error includes `active_operation` with its tool, phase, elapsed time and operation ID when available. The wait hint points to `get_operation_result` for retained jobs or `get_context(scope="progress")` for other requests.

`get_operation_result` returns the retained operation-time snapshot and separate current Undo, continuation and runtime state. Results are retained up to 64 records and 16 MiB per editor session, evicting completed records first; missing or expired records return explicit errors. Source continuations are bounded separately to 32 running or blocked bundles, and blocked continuations may expire before their receipt. Read bases retain up to 256 versions and 16 MiB. Editor restart clears this session state.

## Asset listing

Use `find_assets` with `{"mode":"list","scope":"res://"}` to list project files, directories and unsaved source drafts without a search term. Set `recursive:false` for immediate children. Listing does not load source bodies. Name, content and symbol searches use a nonempty substring query; `*` is not a wildcard. Dot paths and symlinks are excluded, and pagination and incomplete coverage are explicit.

## Asset deletion and recovery

`delete_assets` is a preview/apply workflow. Preview the exact paths, then apply the returned `plan_id`:

```json
{"action":{"preview":{"paths":["res://old.tres"],"mode":"recoverable","references":"block","include_unsaved":[]}}}
```

`mode` defaults to `recoverable`; `references` defaults to `block`. Use `mode:"permanent"` only when you explicitly want deletion with no Undo or recovery copy. `include_unsaved` must explicitly name targeted `.gd` or `.gdshader` buffers or drafts. Preview is allowed while the game is running, but then reports `can_apply:false` and an `apply_prerequisite` to stop it. The apply guard remains enforced. The preview reports `can_apply` and `blockers`; revision, folder, or reference changes after preview return `STALE_PLAN`, so create a fresh preview.

```json
{"action":{"apply":{"plan_id":"asset-plan-<editor-epoch>-<id>"}}}
```

Recoverable deletion moves files, UID files, and import sidecars into the project-local `.godot-mcp/deletions` directory and preserves targeted unsaved drafts. Project/configuration, cache, and plugin paths are protected. Deletion results report per-path `applied`, `remaining`, and `failures`; `editor_sync` is a separate filesystem scan state. A `pending` result supplies an `operation_id`; use `get_operation_result` with optional `wait_ms` to follow it. Optimistic guards detect changes but are not a cross-process filesystem lock, and partial effects remain possible.

Restore with the durable `deletion_id`; `paths` is optional and selects entries (including folders and companion files). Collisions are refused without overwriting. Persistent IDs are discoverable in `get_context.recoverable_deletions`, including restored records that can still be purged. Sources removed with `include_unsaved` return as unsaved buffers or drafts. `undo_edit(edit_id)` uses the same guarded restoration while the deletion is the latest eligible editor action; use `restore_assets` after an editor restart.

```json
{"deletion_id":"deletion-<hex-32>","paths":["res://old.tres"]}
```

`purge_deleted_assets` previews backup-only `deletion_ids` and applies its `plan_id`. Purging is irreversible, invalidates Undo, and removes recovery data. Permanent deletions have no recovery copy.

```json
{"action":{"preview":{"deletion_ids":["deletion-<hex-32>"]}}}
```

Apply this purge plan with the same `action.apply.plan_id` shape shown above. Partial purges identify removed and retained backup entries; they never alter live project assets.

Reference discovery covers known resource dependencies, quoted path literals in current buffers and authored text, open scene properties, known cached resources, and project settings. Dynamically assembled paths, external or hidden references, symlinks, and references outside the project are not guaranteed. `references:"allow_broken"` reports `remaining_references`; it does not rewrite references automatically. Unsaved affected scenes/resources or unsaved reference owners block deletion; `include_unsaved` only authorizes explicitly targeted `.gd`/`.gdshader` sources.

## Diagnostics and runtime provenance

`get_diagnostics` validates current sources, unsaved source dependencies, and live settings. It is separate from historical logs. It may return an `operation_id` when work exceeds `wait_ms`; use `get_operation_result` to wait without repeating validation. Its bounded fingerprint cache may report `cache="compiled"` or `cache="reused"`. Counts are complete only when all requested coverage is fresh; pending or unavailable sources do not establish an error-free result. Snapshots exclude dot caches and symlinks and are bounded to 20,000 files and 512 MiB.

`get_logs` reads historical editor or selected-run entries with `kinds`, `since`, `limit`, and optional `run_id`; editor errors are historical events. `get_diagnostics` validates current source diagnostics. Neither historical log silence nor occurrence alone establishes the current source verdict or resolves a runtime problem.

`run_scene` accepts `save_uris`, optional `revisions`, and `restart`. `save_uris` explicitly lists documents to persist first; other unsaved documents block startup. Its startup source snapshot covers the launch scene, autoloads and declared dependencies, rather than every project file. These hashes do not prove executed behavior, and dynamically loaded assets are not exhaustively covered.

Routine captures, input and runtime observations omit repeated source provenance. Request `get_context` with `scope:"runtime", runtime_details:true` for a fresh comparison. Unrelated added files do not by themselves require a restart. `restart_required:true` is based on observed running scripts differing from current source; unresolved source or resource effects return `null`, and `false` means no restart need was observed within the stated coverage. Use runtime observations, captures or conditions to assess behavior.

## Viewport capture

`capture_viewport` returns a PNG and capture metadata including a `godot://` capture URI, time and scene, pixel size, viewport coordinates, crop, scale, and coordinate mapping. `rect` is a pixel crop. `max_width` and `max_height` explicitly downscale; omitting them preserves the original pixels. A game capture keeps the running view. Editor captures may target `editor_2d`, `editor_3d`, or an `editor_window` (use a `window_id` from `get_context.editor_windows`); a window captures its client area and does not open or activate it. `scene` asserts the active scene. `framing` defaults to `current`; `scene` and `selection` frame editor content, and explicit `bounds_2d`/`bounds_3d` fit the supplied bounds and require non-current framing. Editor captures report `input_supported:false`.
