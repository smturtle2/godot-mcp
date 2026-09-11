# State and recovery

## Document operation results

`create_script`, `edit_script`, `apply_script_changes`, and `save_documents` use one canonical document result. Each `documents[]` record is keyed by URI and owns the current revision, saved state, conflict metadata, validation state, live reload state, and save effect. The operation owns only the batch outcome: `status`, `complete`, `failures`, `pending_save`, and `undo`. `failures[]` preserves the failed phase, target, details, and executable `recovery` arguments.

The default response is a compact receipt. It keeps the operation ID, document effects and state, validation state and checked revision, conflicts, undo scope, and every failure or recovery field. Routine diagnostic entries and detailed operation fields remain in the retained snapshot; `pending_save` may be omitted when the document state already makes the unsaved effect clear. Use `get_operation_result(operation_id)` for the detailed operation-time snapshot and current Undo eligibility; do not rerun a mutation to obtain details. The result store retains at most 64 records and 16 MiB of serialized result bytes, evicts completed records first, and loses records when the editor restarts. An oversized completed result expires; an oversized pending result remains identified but unavailable until a later publication. Operation IDs are distinct from Undo `edit_id` values.

A document's `revision` is the current live/editor text revision. An omitted validation revision means that document revision was checked. A different checked revision is retained with `state="pending"`, so its verdict does not describe the current text. Document `state="saved"` means the current source matches disk; an attachment can still be applied in the editor and require its own save/undo boundary.

## Resource targets

A resource target is exactly one of these forms:

```json
{"uri": "res://material.tres"}
```

```json
{"node": {"scene": "res://main.tscn", "path": "Sprite", "property": "material"}}
```

Do not combine the forms. Resource mutation uses an explicit named scope:

```json
{"target": {"local": {"node": {"scene": "res://main.tscn", "path": "Sprite", "property": "material"}}}, "set": {"albedo": {"$type": "Color", "r": 1, "g": 0.5, "b": 0, "a": 1}}}
```

```json
{"target": {"shared": {"uri": "res://material.tres"}}, "set": {"albedo": {"$type": "Color", "r": 1, "g": 0.5, "b": 0, "a": 1}}}
```

Read the returned users and import provenance before choosing shared scope.

## Source revisions

`read_script` reads the current editor buffer or draft. Its `revision` describes that text, `disk_revision` describes the current file, and `base_disk_revision` identifies the file revision on which the buffer was based. `baseline_known=false` means the plugin first observed an already modified buffer without enough saved history to establish that baseline.

An `external_change` or `baseline_unknown` conflict blocks automatic source persistence and validation. Scene saves also check for source conflicts because Godot can save linked source resources alongside a scene. Reconcile the editor buffer with the disk file through the editor, then read a fresh revision before editing or saving again. Returning to identical buffer and disk contents clears the conflict.

`create_script` saves its new source before validation. A failed compile or attachment leaves that file in place. Repair the source using `edit_script`; each attachment failure in `failures` includes executable `recovery.tool` and `recovery.arguments` fields. After validation succeeds, use that recovery call to attach the existing script through `update_nodes`, or a shader through `update_resource`. Node scripts must derive from a compatible node type. Attachment changes have their own undo and save boundary.

## Runtime input

Without `capture_uri`, input `position` and `relative` use viewport coordinates. With a capture URI, both use capture image pixels. Positions include the crop origin and resize conversion; relative movement applies only the scale. Mouse button state is maintained across events and calls, including explicit release and `release_after`. Wheel input is momentary.

`send_input` may apply all requested events and then fail its condition wait or capture. Such a result retains `processed`, `held_inputs`, stage results and `failures`, with `status="partial"`, `complete=false`, and MCP `isError=true`. A requested condition timeout also produces this outcome. Retry the failed observation or capture rather than replaying the input sequence. A standalone `wait_for_condition` timeout remains an observation with `timed_out=true`.

## Named mutation inputs

Script edits select one change payload:

```json
{"change": {"replace": {"uri": "res://main.gd", "if_revision": "<revision>", "source": "extends Node\n"}}}
```

Animation tracks, TileSet changes, input events, conditions, and node creation use the same JSON Schema rule: exactly one named property carries the payload. For example, a TileSet change is `{"add_physics_layer": {}}`, an input event is `{"event": {"action": {"action": "ui_accept", "pressed": true}}}`, and a wait condition is `{"property": {"node": {"run_id": "<run_id>", "path": "/root/Main"}, "property": "visible", "value": true}}`. TileSet targets select `local` or `shared` explicitly; `edit_animation` uses `local` or `shared` scope.

Node creation selects exactly one source per node:

```json
{"parent": {"scene": "res://main.tscn", "path": "."}, "nodes": [{"name": "Sprite", "source": {"class": "Sprite2D"}}]}
```

Animation track changes select one operation such as `{"add": {"kind": "value", "path": "Sprite:position", "keys": []}}` inside a track. A TileSet batch keeps its named changes together for one staged commit and one Undo.

## Asset imports

`import_assets` creates an operation record before writing files. A wait timeout returns its `operation_id`, applied `files_written` and `options_changed`, pending phase, and `undo_state="pending"`. Godot may continue importing after this response. Query the same operation instead of submitting the same paths again:

```json
{"operation_id": "<returned operation_id>"}
```

Pass this to `get_operation_result` for the detailed snapshot. `get_context` lists only pending import executions. Overlapping imports are rejected while the import manager owns those paths.

Once the importer is quiet, the operation records its final changes and registers undo when needed. Use the returned `edit_id` only when `undo_state="available"`. Undo checks both editor history and finalized file contents. If a source changes externally during a pending operation, continuation stops with `IMPORT_CONFLICT`, preserves the file and reports undo as unavailable. This journal does not provide atomic rollback against concurrent external writers. The import manager retains only pending executions, with up to 32 active records; result snapshots follow the shared 64-record/16 MiB limits.

## Diagnostics

`get_diagnostics.kinds` filters editor logs, runtime logs and source entries. Log filtering happens before `limit`; use the returned cursor for the next page. `has_more` indicates further entries matching the filter. Filtering source messages does not change their validation verdict.

Validation snapshots exclude caches and symlinks without following the links. An unrelated symlink does not prevent checking regular sources. Sources whose dependencies cannot be resolved because paths were excluded report `state="unavailable"` and `valid=null`. Snapshots are limited to 20,000 files and 512 MiB. Truncated compiler output also produces an unavailable verdict; export results separately report `output_truncated`.
