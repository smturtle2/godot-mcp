# State and recovery

## Resource targets

A resource target is exactly one of these forms:

```json
{"uri": "res://material.tres"}
```

```json
{"node": {"scene": "res://main.tscn", "path": "Sprite"}, "property": "material"}
```

Do not combine the forms. `scope="node"` requires a node property target and isolates that node's resource. `scope="shared"` edits the resolved resource and may use either selector. Read the returned users and import provenance before choosing shared scope.

## Source revisions

`read_script` reads the current editor buffer or draft. Its `revision` describes that text, `disk_revision` describes the current file, and `base_disk_revision` identifies the file revision on which the buffer was based. `baseline_known=false` means the plugin first observed an already modified buffer without enough saved history to establish that baseline.

An `external_change` or `baseline_unknown` conflict blocks automatic source persistence and validation. Scene saves also check for source conflicts because Godot can save linked source resources alongside a scene. Reconcile the editor buffer with the disk file through the editor, then read a fresh revision before editing or saving again. Returning to identical buffer and disk contents clears the conflict.

`create_script` saves its new source before validation. A failed compile or attachment leaves that file in place. Repair the source using `edit_script`; each `attachment_errors` entry includes an executable `retry.tool` and `retry.arguments`. After validation succeeds, use that retry to attach the existing script through `update_nodes`, or a shader through `update_resource`. Node scripts must derive from a compatible node type. Attachment changes have their own undo and save boundary.

## Runtime input

Without `capture_uri`, input `position` and `relative` use viewport coordinates. With a capture URI, both use capture image pixels. Positions include the crop origin and resize conversion; relative movement applies only the scale. Mouse button state is maintained across events and calls, including explicit release and `release_after`. Wheel input is momentary.

`send_input` may apply all requested events and then fail its condition wait or capture. Such a result retains `processed`, `held_inputs`, stage results and `failures`, with `status="partial"`, `complete=false`, and MCP `isError=true`. A requested condition timeout also produces this outcome. Retry the failed observation or capture rather than replaying the input sequence. A standalone `wait_for_condition` timeout remains an observation with `timed_out=true`.

## Asset imports

`import_assets` creates an operation record before writing files. A wait timeout returns its `operation_id`, applied `files_written` and `options_changed`, pending phase, and `undo_state="pending"`. Godot may continue importing after this response. Query the same operation instead of submitting the same paths again:

```json
{"scope": "operations", "operation_id": "<returned operation_id>"}
```

Pass this to `get_context`. Its default context also lists pending imports. Overlapping imports are rejected while the operation owns those paths.

Once the importer is quiet, the operation records its final changes and registers undo when needed. Use the returned `edit_id` only when `undo_state="available"`. Undo checks both editor history and finalized file contents. If a source changes externally during a pending operation, continuation stops with `IMPORT_CONFLICT`, preserves the file and reports undo as unavailable. This journal does not provide atomic rollback against concurrent external writers. Operation records last for the current editor session, with up to 32 retained records.

## Diagnostics

`get_diagnostics.kinds` filters editor logs, runtime logs and source entries. Log filtering happens before `limit`; use the returned cursor for the next page. `has_more` indicates further entries matching the filter. Filtering source messages does not change their validation verdict.

Validation snapshots exclude caches and symlinks without following the links. An unrelated symlink does not prevent checking regular sources. Sources whose dependencies cannot be resolved because paths were excluded report `state="unavailable"` and `valid=null`. Snapshots are limited to 20,000 files and 512 MiB. Truncated compiler output also produces an unavailable verdict; export results separately report `output_truncated`.
