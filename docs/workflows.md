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

`save` defaults to `false` for both Add and Update, leaving live editor changes as drafts. `save: true` persists sources before validation and saves binding owners after successful binding work. Saved source remains on disk if a later validation phase fails. Source changes already applied remain available for repair after a compile or binding failure.

One operation coordinates these phases, in order: `source`, `save_sources`, `validation`, `editor_reload`, `bindings`, and `save_bindings`. A `pending` response includes `operation_id`; call `get_operation_result` with that ID (and optional `wait_ms`) to wait for the same work without replaying it. The operation result reports per-document state, validation and save effects, failures with phase and recovery details, pending work, and Undo information.

`resume_script_changes` continues blocked or unfinished phases without replaying the patch or successful bindings. It preserves completed bindings. After repairing text, provide a current read revision for every original source in `revisions`; accepting repaired text without all original source revisions is rejected. Changes made to the targets while the operation was blocked still cause conflicts.

Source changes retain one Undo action plus binding steps in newest-first order. Disk files are preserved. Saving a scene can include linked edited sources; if the scope is incomplete, the operation fails with `SAVE_SCOPE_REQUIRED` and reports the additional URIs to pass explicitly to `save_documents`.

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

`get_context` reports pending source, diagnostic, and import jobs, along with project/editor/runtime state. Import executions are bounded per editor session; result snapshots share the operation retention limits.

`get_operation_result` returns the retained operation-time snapshot and separate current Undo, continuation and runtime state. Results are retained up to 64 records and 16 MiB per editor session, evicting completed records first; missing or expired records return explicit errors. Source continuations are bounded separately to 32 running or blocked bundles, and blocked continuations may expire before their receipt. Read bases retain up to 256 versions and 16 MiB. Editor restart clears this session state.

## Diagnostics and runtime provenance

`get_diagnostics` validates current sources, unsaved source dependencies, and live settings. It is separate from historical logs. It may return an `operation_id` when work exceeds `wait_ms`; use `get_operation_result` to wait without repeating validation. Its bounded fingerprint cache may report `cache="compiled"` or `cache="reused"`. Counts are complete only when all requested coverage is fresh; pending or unavailable sources do not establish an error-free result. Snapshots exclude dot caches and symlinks and are bounded to 20,000 files and 512 MiB.

`get_logs` reads historical editor or selected-run entries with `kinds`, `since`, `limit`, and optional `run_id`. Historical log occurrence or silence does not establish the current source verdict or resolve a runtime problem.

`run_scene` accepts `save_uris`, optional `revisions`, and `restart`. `save_uris` explicitly lists documents to persist first; other unsaved documents block startup. Startup file hashes identify source state at launch but do not prove executed behavior. Runtime results include `source_provenance`; after edits they report `source_changed` and `restart_required` when a restart is needed. Use runtime observations, captures, or conditions to assess behavior.
