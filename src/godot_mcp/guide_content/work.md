# Working with the Godot project

Paths in tool arguments are project URIs such as `res://main.tscn`; local files supplied to import or export use `file:///...`. Node references contain both the scene URI and a relative node path. Values returned by the server are authoritative: use returned node references, resource URIs, run IDs, capture URIs, revisions, operation IDs, plan IDs, and deletion IDs in later calls. In examples below, angle-bracket values are placeholders for those returned values.

For shared rules about revisions, scopes, and operation receipts, see `get_guide` section `model`. For recovery of pending work, stale plans, conflicts, or deletions, see `get_guide` section `recovery`.

## Scenes and nodes

Start by reading the project and editor state:

```json
{}
```

Call `get_context` with that argument to learn the active scene, selection, unsaved documents, pending operations, and runtime state. Inspect a scene with `get_scene`:

```json
{
  "scene": "res://main.tscn",
  "path": ".",
  "include": ["properties", "connections", "layout"],
  "depth": 2
}
```

`open_scene` activates a saved scene when you need to inspect or work in that editor scene:

```json
{"scene":"res://main.tscn"}
```

Create a new saved scene by providing a root name and either a root class or inherited source:

```json
{
  "uri": "res://level.tscn",
  "root_class": "Node2D",
  "root_name": "Level"
}
```

The result supplies the actual root reference. Use it when creating related nodes. Every node source is exactly one of `class`, `instance`, or `duplicate`. Related nodes can use `parent_key` to refer to a matching `key` in the same batch:

```json
{
  "parent": {"scene":"res://level.tscn","path":"."},
  "nodes": [
    {"key":"player","name":"Player","source":{"class":"CharacterBody2D"}},
    {"name":"Camera2D","parent_key":"player","source":{"class":"Camera2D"}}
  ]
}
```

Use `instance` with a PackedScene URI, or `duplicate` with an existing `{scene, path}` reference. `update_nodes` batches property changes, renames, reparenting, and sibling index changes:

```json
{
  "changes": [
    {"node":{"scene":"res://level.tscn","path":"Player"},"set":{"position":{"$type":"Vector2","x":120,"y":80}}},
    {"node":{"scene":"res://level.tscn","path":"Player"},"name":"Hero"}
  ]
}
```

Use `delete_nodes` for related nodes and retain its `edit_id` if you may need `undo_edit`. Inherited members, overlapping selections, and persistent references can constrain deletion. Save authored scenes and scripts explicitly with `save_documents`:

```json
{"uris":["res://level.tscn","res://player.gd"]}
```

Saving and validation are separate operations. If a scene save would include additional edited authored documents, the server reports the paths to add.

## Sources, bindings, and resources

Read scripts before editing so the patch can be guarded by the returned revision:

```json
{"documents":[{"uri":"res://player.gd"},{"uri":"res://ui.gd","symbol":"build"}]}
```

Pass the relevant `base_revisions` to `apply_script_changes`. Its patch language is exact and context based:

```json
{
  "patch":"*** Begin Patch\n*** Update File: res://player.gd\n@@\n func _ready():\n-    print(\"old\")\n+    print(\"ready\")\n*** End Patch",
  "base_revisions":{"res://player.gd":"<sha256-revision>"},
  "save":true
}
```

The revision placeholder must be the actual 64-character revision returned by `read_scripts` or `find_assets`; do not invent one. A patch can add or update several sources and can attach a script or shader and connect signals in the same operation. Script attachments name a node; shader attachments require an explicitly scoped ShaderMaterial target:

```json
{
  "patch":"*** Begin Patch\n*** Add File: res://toon.gdshader\n+shader_type canvas_item;\n*** End Patch",
  "attachments":[
    {"shader":{"uri":"res://toon.gdshader","target":{"local":{"scene":"res://level.tscn","path":"Player","property":"material"}}}}
  ],
  "connections":{"connect":[],"disconnect":[]},
  "save":true
}
```

Use `update_signals` when only persistent signal connections change. `resume_script_changes` continues a blocked or unfinished source operation by its returned operation ID; it does not replay completed work. Use `get_operation_result` to poll any pending operation instead of submitting the mutation again.

Resources can be selected by URI or by a node property. Inspect users and import provenance with `get_resource`:

```json
{"target":{"node":{"scene":"res://level.tscn","path":"Player","property":"material"}},"depth":2}
```

Create an in-memory resource and save an authored copy:

```json
{
  "class":"StandardMaterial3D",
  "properties":{"roughness":0.6},
  "save_as":"res://player_material.tres"
}
```

For existing resources, `update_resource` requires either a `local` node-property target or a `shared` resource target. Imported shared sources must first be detached into an authored resource. Use the scope that matches the intended sharing behavior.

## Assets: list, import, move, and delete

List files, directories, and live source drafts with `find_assets`; list mode does not load source bodies:

```json
{"mode":"list","scope":"res://","recursive":false}
```

For name, content, or symbol search, provide a nonempty substring query. `types` accepts comma-separated alternatives in each type filter; `*` is not a wildcard. Use returned pagination data when coverage is incomplete.

Copy a local file into the project or reimport it with `import_assets`:

```json
{
  "files":[
    {"source":"file:///tmp/player.png","destination":"res://art/player.png","overwrite":true}
  ]
}
```

Import can return a pending operation ID while Godot writes, imports, or settles. Query that ID with `get_operation_result`; do not repeat the same paths. `move_assets` updates project paths, UID sidecars, and serialized dependencies:

```json
{"moves":[{"from":"res://art/player.png","to":"res://art/hero.png"}]}
```

Deletion is intentionally a two-call preview/apply workflow. Preview exact paths and choose the reference policy:

```json
{
  "action":{"preview":{
    "paths":["res://old.tres"],
    "mode":"recoverable",
    "references":"block",
    "include_unsaved":[]
  }}
}
```

Apply only the returned plan ID:

```json
{"action":{"apply":{"plan_id":"<asset-plan-id>"}}}
```

Recoverable deletion preserves files and companions in the project-local recovery area and returns a durable `deletion_id`; `restore_assets` uses that ID. `mode:"permanent"` has no recovery or Undo. Purge recovery backups only after previewing their deletion IDs with `purge_deleted_assets`.

## Animation and tiles

Inspect an AnimationPlayer or AnimationTree with `get_animation`, then use `edit_animation` for typed tracks. A track chooses one kind such as `value`, `position_3d`, `rotation_3d`, `scale_3d`, `method`, or `bezier`; keys choose `set` or `remove`:

```json
{
  "player":{"scene":"res://level.tscn","path":"Player/AnimationPlayer"},
  "name":"blink",
  "create":true,
  "length":1.0,
  "loop":true,
  "scope":"local",
  "tracks":[{"add":{"kind":"value","path":".:modulate","keys":[{"set":{"time":0,"value":{"$type":"Color","r":1,"g":1,"b":1,"a":1}}}]}}]
}
```

Use `edit_animation_graph` for state machines, blend trees, transitions, connections, and parameters. `preview_animation` evaluates an editor pose at a time and can capture the real editor viewport; method and audio tracks are not executed.

Use `get_tilemap` to inspect bounded cells and identifiers. `edit_tileset` changes an explicitly scoped local or shared TileSet with changes such as `add_atlas`, `define_tile`, collision, and terrain operations. `paint_tiles` paints cells, regions, patterns, or terrain paths:

```json
{
  "layer":{"scene":"res://level.tscn","path":"Ground"},
  "cells":[{"cell":{"x":2,"y":3},"tile":{"source_id":0,"atlas":{"x":1,"y":0},"alternative":0}}]
}
```

## Run, input, capture, and debugging

Start a scene with `run_scene`, explicitly naming any authored documents that must be saved first:

```json
{"scene":"res://level.tscn","save_uris":["res://player.gd"],"restart":true}
```

Use the returned `run_id` with `inspect_runtime`, `wait_for_condition`, `send_input`, `capture_viewport`, `sample_performance`, and `stop_game`. A runtime node reference is `{run_id, path}` and its path starts at `/root`:

```json
{"node":{"run_id":"<run-id>","path":"/root/Level/Player"},"depth":1}
```

Inject named events with `send_input`; action events are convenient for configured controls:

```json
{
  "run_id":"<run-id>",
  "events":[{"event":{"action":{"action":"ui_accept","pressed":true}}}],
  "capture_after":true,
  "release_after":true
}
```

Key, mouse button, mouse motion, touch, drag, and action events are each explicit variants. Without `capture_uri`, pointer coordinates use viewport pixels. With a capture URI, they use capture pixels; held mouse and key state persists until released. If observation or capture fails after input was applied, retry the observation rather than replaying the input.

`capture_viewport` can capture `game`, `editor_2d`, `editor_3d`, or an `editor_window`. A game capture uses the run ID; editor-window capture uses a `window_id` from `get_context.editor_windows`. The result includes a `godot://` capture URI, dimensions, crop, scale, and coordinate mapping. Pass that URI to later input when coordinate alignment matters.

For current source validation, call `get_diagnostics`; it reports a captured snapshot and may return an operation ID. Use `get_logs` for historical editor or run entries. They answer different questions: logs show history, while diagnostics validate the requested snapshot. For a suspended GDScript run, use `inspect_debugger` with the returned `pause_id` or frame handles, then `debug_control` with `pause`, `continue`, `step_over`, or `step_into`. Frame handles become stale after continuing. `set_breakpoints` manages MCP-owned breakpoints while preserving user breakpoints.

## Settings and export

Read settings, input mappings, and autoloads with `get_settings`:

```json
{"include":["project","input_actions","autoload"]}
```

Apply changes with `update_settings`. Input mapping events use `type` values such as `key`, `mouse_button`, `joypad_button`, and `joypad_motion`; autoload entries name a project URI. Save `project.godot` explicitly through `save_documents` when persistence is required.

Inspect real preset names and template readiness before exporting:

```json
{"preset":"<preset-name>"}
```

Then call `export_build` with that preset and a local output file:

```json
{
  "preset":"<preset-name>",
  "output":"file:///tmp/level-build.zip",
  "debug":false,
  "timeout_ms":120000
}
```

Export verification confirms that the artifact exists; it does not establish that the exported application executes correctly. Run and observe the project separately when behavior matters.
