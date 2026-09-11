"""Executable tool contracts shared by the MCP server, tests, and docs generator."""
from __future__ import annotations


def obj(properties: dict, required: tuple = (), **constraints) -> dict:
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False, **constraints}


def arr(items: dict, maximum: int = 200, minimum: int = 0) -> dict:
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum}


def enum(*values: str) -> dict:
    return {"type": "string", "enum": list(values)}


def integer(low: int = 0, high: int = 2147483647) -> dict:
    return {"type": "integer", "minimum": low, "maximum": high}


S = {"type": "string", "minLength": 1, "maxLength": 4096}
TEXT = {"type": "string", "maxLength": 1_000_000}
B = {"type": "boolean"}

NULLABLE_STRING = {"type": ["string", "null"]}
DIAGNOSTIC_ENTRY = {"type": "object", "properties": {"kind": enum("error", "warning", "log"), "uri": {"type": "string"}, "line": integer(), "message": TEXT, "cursor": integer(), "time_usec": integer(), "count": integer(1)}, "additionalProperties": True}
DOCUMENT_STATE = {"type": "object", "properties": {"uri": {"type": "string"}, "state": enum("saved", "modified", "draft", "unavailable"), "revision": NULLABLE_STRING, "disk_revision": NULLABLE_STRING, "saved": B, "live_reload": enum("succeeded", "failed", "deferred")}, "required": ["uri", "state"], "additionalProperties": True}
VALIDATION_SOURCE = {"type": "object", "properties": {"uri": {"type": "string"}, "revision": NULLABLE_STRING, "state": enum("valid", "invalid", "pending", "unavailable"), "valid": {"type": ["boolean", "null"]}, "scope": {"const": "snapshot"}, "entries": arr(DIAGNOSTIC_ENTRY, 2000)}, "required": ["uri", "revision", "state", "valid", "scope", "entries"], "additionalProperties": True}
VALIDATION_RESULT = {"type": "object", "properties": {"sources": arr(VALIDATION_SOURCE, 100), "snapshot_id": S, "source_revisions": {"type": "object", "additionalProperties": {"type": "string"}}}, "required": ["sources"], "additionalProperties": True}
UNDO_RESULT = {"type": "object", "properties": {"edit_id": NULLABLE_STRING, "scope": arr(S, 16), "retained_files": arr({"type": "string"}, 200), "note": TEXT}, "additionalProperties": True}
ERROR_RESULT = {"type": "object", "properties": {"error": {"type": "object", "properties": {"code": S, "message": TEXT, "details": {"type": "object", "additionalProperties": True}}, "required": ["code", "message", "details"], "additionalProperties": True}}, "required": ["error"], "additionalProperties": True}


def output_schema(properties: dict, required: tuple = ()) -> dict:
    success = {"type": "object", "properties": properties, "required": list(required), "additionalProperties": True, "not": {"required": ["error"]}}
    return {"type": "object", "oneOf": [success, ERROR_RESULT]}


N = {"type": "number"}
RES = {"type": "string", "pattern": r"^res://(?!.*(?:^|/)\.\.(?:/|$))(?!.*\\).+", "maxLength": 4096}
FILE = {"type": "string", "pattern": r"^file:///", "maxLength": 4096}
NODE_PATH = {"type": "string", "minLength": 1, "maxLength": 2048,
             "pattern": r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*:).+"}
REF = obj({"scene": RES, "path": NODE_PATH}, ("scene", "path"))
RUN_REF = obj({"run_id": S, "path": {"type": "string", "pattern": "^/root(?:/|$)", "maxLength": 2048}}, ("run_id", "path"))
RESOURCE = obj({"uri": {"type": "string", "pattern": r"^(?:res://|godot://resources/).+"},
                "node": REF, "property": S}, oneOf=[{"required": ["uri"]}, {"required": ["node", "property"]}])
V2 = obj({"x": N, "y": N}, ("x", "y"))
I2 = obj({"x": integer(-1_000_000, 1_000_000), "y": integer(-1_000_000, 1_000_000)}, ("x", "y"))
SIZE = obj({"x": integer(1, 4096), "y": integer(1, 4096)}, ("x", "y"))
VALUE = {"description": "JSON or tagged Godot value ($type, with named components). Resource uses a returned uri; Color space is linear or srgb."}
PROPS = {"type": "object", "maxProperties": 200, "additionalProperties": VALUE}
POSITION = obj({"line": integer(1, 1_000_000), "column": integer(1, 1_000_000)}, ("line", "column"))
RANGE = obj({"start": POSITION, "end": POSITION}, ("start", "end"))
REGION = obj({"origin": I2, "size": SIZE}, ("origin", "size"))
TILE = obj({"source_id": integer(-1), "atlas": I2, "alternative": integer()}, ("source_id",))
CELL = obj({"cell": I2, "tile": TILE}, ("cell", "tile"))
SIGNAL = obj({"from": REF, "signal": S, "to": REF, "method": S, "binds": arr(VALUE, 16)}, ("from", "signal", "to", "method"))
CONDITION = obj({"type": enum("scene", "node", "property", "signal"), "uri": RES,
                 "node": RUN_REF, "property": S, "operator": enum("eq", "ne", "gt", "gte", "lt", "lte"),
                 "value": VALUE, "exists": B, "signal": S}, ("type",),
                allOf=[{"if": {"properties": {"type": {"const": k}}}, "then": {"required": req}}
                       for k, req in [("scene", ["uri"]), ("node", ["node"]),
                                      ("property", ["node", "property", "value"]), ("signal", ["node", "signal"])]])
INPUT_COMMON = {"at_ms": {**integer(0, 60_000), "description": "Milliseconds from batch start; events must be nondecreasing."}}
MODIFIERS = {"shift": B, "ctrl": B, "alt": B, "meta": B}
INPUT = {"oneOf": [
    obj({"type": {"const": "key"}, **INPUT_COMMON, "key": {**S, "description": "Godot key name."},
         "pressed": {**B, "description": "Whether the key is pressed or released."}, "physical": B, **MODIFIERS},
        ("type", "key", "pressed")),
    obj({"type": {"const": "mouse_button"}, **INPUT_COMMON, "button": enum("left", "right", "middle", "wheel_up", "wheel_down"),
         "position": {**V2, "description": "Pointer position in viewport or capture coordinates."},
         "pressed": {**B, "description": "Whether the button is pressed or released."}, **MODIFIERS},
        ("type", "button", "position", "pressed")),
    obj({"type": {"const": "mouse_motion"}, **INPUT_COMMON,
         "position": {**V2, "description": "Pointer position in viewport or capture coordinates."}, "relative": V2, **MODIFIERS},
        ("type", "position")),
    obj({"type": {"const": "touch"}, **INPUT_COMMON,
         "position": {**V2, "description": "Touch position in viewport or capture coordinates."}, "pressed": B, "index": integer(0, 15)},
        ("type", "position", "pressed")),
    obj({"type": {"const": "drag"}, **INPUT_COMMON,
         "position": {**V2, "description": "Touch position in viewport or capture coordinates."}, "relative": V2, "index": integer(0, 15)},
        ("type", "position", "relative")),
    obj({"type": {"const": "action"}, **INPUT_COMMON, "action": {**S, "description": "Defined Godot input action name."},
         "pressed": {**B, "description": "Whether the action is pressed or released."},
         "strength": {"type": "number", "minimum": 0, "maximum": 1}}, ("type", "action", "pressed")),
]}
# Describe object fields directly for clients that do not render union branches.
# The oneOf variants still enforce each event's required and permitted fields.
INPUT.update(type="object", properties={key: value for variant in INPUT["oneOf"] for key, value in variant["properties"].items()})
INPUT["properties"]["type"] = enum("key", "mouse_button", "mouse_motion", "touch", "drag", "action")
MAPPING_EVENT = obj({"type": enum("key", "mouse_button", "joypad_button", "joypad_motion"), "key": S,
                     "physical": B, "button": integer(0, 32), "axis": integer(0, 15), "axis_value": N,
                     "shift": B, "ctrl": B, "alt": B, "meta": B}, ("type",))
NODE_SPEC = obj({"key": {**S, "description": "Optional unique logical identifier for this record."},
                 "parent_key": {**S, "description": "Optional logical parent key; omitted means the tool parent."},
                 "name": {**S, "description": "Node name."}, "class": {**S, "description": "Node class to instantiate."},
                 "instance": {**RES, "description": "PackedScene URI to instantiate."},
                 "duplicate": {**REF, "description": "Live node reference to duplicate."}, "properties": PROPS}, ("name",),
                oneOf=[{"required": ["class"]}, {"required": ["instance"]}, {"required": ["duplicate"]}])
SOURCE_RESULT = {"uri": RES, "source": TEXT, "revision": S, "disk_revision": NULLABLE_STRING, "exists_on_disk": B, "unsaved": B, "buffer": S, "external_change": B, "symbols": arr({"type": "object", "additionalProperties": True}, 10000), "range": RANGE}
CREATE_SCRIPT_OUTPUT = output_schema({"uri": RES, "revision": S, "saved": B, "diagnostics": VALIDATION_SOURCE, "attached": arr({"type": "object", "additionalProperties": True}, 50), "attachment_errors": arr({"type": "object", "additionalProperties": True}, 50), "status": enum("completed", "partial", "failed"), "summary": TEXT, "document": DOCUMENT_STATE, "undo": UNDO_RESULT, "pending_save": arr(S, 200)}, ("uri", "revision", "saved", "diagnostics", "attached", "attachment_errors", "status", "summary", "document", "undo", "pending_save"))
EDIT_SCRIPT_OUTPUT = output_schema({"uri": RES, "revision": S, "saved": B, "diagnostics": VALIDATION_SOURCE, "runtime_application": S, "documents": arr(DOCUMENT_STATE, 100), "validation": VALIDATION_RESULT, "persistence": {"type": "object", "additionalProperties": True}, "pending_save": arr(S, 200), "status": enum("completed", "partial", "failed"), "summary": TEXT, "undo": UNDO_RESULT, "edit_id": NULLABLE_STRING}, ("uri", "revision", "saved", "diagnostics"))
APPLY_SCRIPT_OUTPUT = output_schema({"documents": arr(DOCUMENT_STATE, 100), "validation": VALIDATION_RESULT, "persistence": {"type": "object", "additionalProperties": True}, "pending_save": arr(S, 200), "status": enum("completed", "partial", "failed"), "summary": TEXT, "undo": UNDO_RESULT, "saved": B, "edit_id": NULLABLE_STRING}, ("documents", "validation", "persistence", "pending_save", "status", "summary", "undo", "saved"))
SAVE_DOCUMENTS_OUTPUT = output_schema({"saved": arr({"type": "object", "additionalProperties": True}, 200), "failed": arr({"type": "object", "additionalProperties": True}, 200), "also_saved": arr(RES, 200), "also_saved_scope": TEXT, "complete": B, "status": enum("completed", "partial", "failed"), "summary": TEXT, "undo": UNDO_RESULT}, ("saved", "failed", "complete", "status", "summary", "undo"))
READ_SCRIPT_OUTPUT = output_schema(SOURCE_RESULT, ("uri", "source", "revision", "symbols"))
DIAGNOSTICS_OUTPUT = output_schema({"entries": arr(DIAGNOSTIC_ENTRY, 1000), "sources": arr(VALIDATION_SOURCE, 200), "entries_are_history": B, "origin": S, "snapshot_id": S, "runtime": {"type": "object", "additionalProperties": True}}, ("entries", "sources", "entries_are_history", "origin"))
SCRIPT_CHANGE = {"oneOf": [
        obj({"uri": RES, "create": {"const": True}, "source": TEXT}, ("uri", "create", "source")),
        obj({"uri": RES, "create": B, "if_revision": S, "source": TEXT}, ("uri", "if_revision", "source"),
            **{"not": {"required": ["create"], "properties": {"create": {"const": True}}}}),
        obj({"uri": RES, "create": B, "if_revision": S, "edits": arr(obj({"range": RANGE, "text": TEXT}, ("range", "text")), 200, 1)}, ("uri", "if_revision", "edits"),
            **{"not": {"required": ["create"], "properties": {"create": {"const": True}}}}),
    ]}
SCRIPT_CHANGE.update(type="object", properties={key: value for variant in SCRIPT_CHANGE["oneOf"] for key, value in variant["properties"].items()})


TRACK = obj({"op": enum("add", "update", "remove"), "index": integer(),
             "kind": enum("value", "position_3d", "rotation_3d", "scale_3d", "method", "bezier"), "path": S,
             "interpolation": enum("nearest", "linear", "cubic"), "enabled": B, "replace_keys": B,
             "keys": arr(obj({"time": {"type": "number", "minimum": 0}, "value": VALUE, "transition": N,
                               "remove": B}, ("time",)), 5000)},
            anyOf=[{"required": ["index"]}, {"required": ["kind", "path"]}])
GRAPH_NODE = obj({"name": S, "kind": enum("animation", "blend2", "add2", "blend3", "one_shot", "time_scale", "time_seek", "blend_space_1d", "blend_space_2d"),
                  "animation": S, "position": V2, "min": VALUE, "max": VALUE,
                  "points": arr(obj({"animation": S, "position": VALUE}, ("animation", "position")), 64),
                  "filter": arr(S, 200)}, ("name", "kind"))
TS_CHANGE = obj({"op": enum("add_atlas", "define_tile", "remove_tile", "add_physics_layer", "collision", "add_terrain_set", "terrain"),
                 "key": S, "source_key": S, "source_id": integer(), "texture": RES, "tile_size": SIZE,
                 "atlas": I2, "size": SIZE, "alternative": integer(), "physics_layer": integer(0, 31),
                 "collision_layer": integer(), "collision_mask": integer(), "polygons": arr(arr(V2, 100, 3), 32),
                 "one_way": B, "terrain_set": integer(), "terrain": integer(-1),
                 "terrains": arr(obj({"name": S, "color": VALUE}, ("name",)), 64),
                 "mode": enum("corners_and_sides", "corners", "sides"),
                 "peering_bits": {"type": "object", "additionalProperties": integer(-1, 255)}, "probability": {"type": "number", "minimum": 0}}, ("op",))


def tool(name, description, properties, required=(), *, read=False, destructive=False, idempotent=False, constraints=None, output=None):
    schema = obj({"project": {"type": "string", "minLength": 1, "description": "Absolute project path; omit after selecting via get_context."}, **properties}, required, **(constraints or {}))
    result = {"name": name, "description": description, "inputSchema": schema,
            "annotations": {"readOnlyHint": read, "destructiveHint": destructive,
                            "idempotentHint": idempotent, "openWorldHint": False}}
    if output is not None:
        result["outputSchema"] = output
    return result


TOOL_SPECS = [
    tool("install_plugin", "Install and enable the bundled plugin in an existing Godot project before connecting to the editor. Close the project in Godot first. Creates a rollback backup and registers project discovery.", {"project": {**S, "description": "Required absolute path to the directory containing project.godot."}}, ("project",)),
    tool("get_context", "Read project/engine/product/protocol versions, active scene, selection, unsaved documents and actual run state.", {"scope": enum("all", "project", "editor", "runtime")}, read=True),
    tool("find_assets", "Search filenames, source text or symbols. Returns reusable res:// URIs and one-based source locations.", {"query": S, "mode": enum("name", "text", "symbol"), "types": arr(S, 32), "scope": {"type": "string", "pattern": "^res://"}, "limit": integer(1, 500)}, ("query",), read=True),
    tool("get_class_info", "Inspect actual engine or project script classes, properties, methods and signals; optionally filter a member.", {"class": S, "member": S}, ("class",), read=True),
    tool("get_scene", "Inspect live scene nodes, unsaved values, connections, inheritance overrides and actual Control layout.", {"scene": RES, "path": NODE_PATH, "properties": {**arr(S), "description": "Property names: omitted means all editor properties when properties is included; [] means none."}, "include": {**arr(enum("properties", "overrides", "connections", "layout"), 4), "description": "Sections to include; omitted means structure only."}, "depth": integer(0, 32)}, read=True),
    tool("open_scene", "Open and activate a saved scene in the editor.", {"scene": RES}, ("scene",), idempotent=True),
    tool("create_scene", "Create a scene with a typed root or inherited source. Saves the new file and returns its root reference.", {"uri": RES, "root_class": S, "root_name": S, "inherits": RES}, ("uri", "root_name")),
    tool("create_nodes", "Create a flat related-node batch using optional parent_key links, scene instances or duplicates in one undoable edit. Returns actual names and references.", {"parent": REF, "nodes": arr(NODE_SPEC, 1000, 1)}, ("parent", "nodes")),
    tool("update_nodes", "Batch node properties, names and reparenting in one scene. Use references in the source scene to edit the original. Container-controlled layout is reported.", {"changes": arr(obj({"node": REF, "set": PROPS, "name": S, "parent": REF, "index": integer(0, 10000), "keep_global_transform": B}, ("node",)), 200, 1)}, ("changes",)),
    tool("delete_nodes", "Delete related nodes with undo; report affected persistent connections and NodePath references. Reject inherited members and overlapping selections.", {"nodes": arr(REF, 200, 1)}, ("nodes",), destructive=True),
    tool("save_documents", "Save requested documents; Godot scene saves may also persist linked resources. Reports observed extra source saves, partial failures, and the separate undo boundary.", {"uris": arr({"type": "string", "pattern": "^(res://|godot://resources/).+"}, 200, 1), "save_as": {"type": "object", "additionalProperties": RES}}, ("uris",), idempotent=True, output=SAVE_DOCUMENTS_OUTPUT),
    tool("undo_edit", "Undo the latest MCP edit if its editor history has not changed since. Filesystem operations report their separate rollback scope.", {"edit_id": S}, ("edit_id",), destructive=True),
    tool("get_resource", "Read resource properties, nested references, known users and import provenance. Sharing scan covers open scenes and indexed project dependencies.", {"target": RESOURCE, "properties": arr(S), "depth": integer(0, 5)}, ("target",), read=True),
    tool("create_resource", "Create an in-memory resource, optionally attach it or save it. Returns a reusable resource URI.", {"class": S, "properties": PROPS, "assign_to": obj({"node": REF, "property": S}, ("node", "property")), "save_as": RES}, ("class",)),
    tool("update_resource", "Change a resource with explicit node-local or shared scope. Imported shared sources require detaching to an authored resource.", {"target": RESOURCE, "set": PROPS, "scope": enum("node", "shared"), "save_as": RES}, ("target", "set", "scope")),
    tool("read_script", "Read the current source, including unsaved editor/store changes, with its revision and symbols. Ranges use one-based Unicode columns and exclusive ends.", {"uri": RES, "symbol": S, "range": RANGE}, ("uri",), read=True, output=READ_SCRIPT_OUTPUT),
    tool("create_script", "Create and save the source before validation; compilation or attachment failures leave the file saved and should be retried with edit_script.", {"uri": RES, "source": TEXT, "attach_to": arr(REF, 50), "material": RESOURCE}, ("uri", "source"), output=CREATE_SCRIPT_OUTPUT),
    tool("edit_script", "Apply a live source edit at an exact revision; changes remain live even when compilation fails, and game hot reload is not promised. Save explicitly to persist.", {"uri": RES, "if_revision": S, "source": TEXT, "edits": arr(obj({"range": RANGE, "text": TEXT}, ("range", "text")), 200, 1)}, ("uri", "if_revision"), constraints={"oneOf": [{"required": ["source"]}, {"required": ["edits"]}]}, output=EDIT_SCRIPT_OUTPUT),
    tool("apply_script_changes", "Apply a bounded batch of live source changes; save=true persists the batch afterward. Changes remain live on compile failure, attachments are outside this batch, and game hot reload is not promised. Validation snapshots exclude caches/symlinks and are limited to 512 MiB and 20,000 files.", {"changes": arr(SCRIPT_CHANGE, 100, 1), "save": {"type": "boolean", "default": False, "description": "Persist the whole batch after application; false leaves live drafts."}}, ("changes",), output=APPLY_SCRIPT_OUTPUT),
    tool("update_signals", "Connect/disconnect persistent signal handlers with optional binds in one scene. Missing handler code is reported.", {"connect": arr(SIGNAL), "disconnect": arr(SIGNAL)}, idempotent=True),
    tool("get_animation", "Inspect animation tracks/keys or AnimationTree states, transitions, blend connections and parameter values.", {"node": REF, "animation": S}, ("node",), read=True),
    tool("edit_animation", "Create or edit an AnimationPlayer animation and typed tracks/keys. Node scope isolates a player's shared library; shared scope is explicit.", {"player": REF, "name": S, "create": B, "length": {"type": "number", "exclusiveMinimum": 0}, "loop": B, "tracks": arr(TRACK), "scope": enum("node", "shared")}, ("player", "name")),
    tool("edit_animation_graph", "Build state machines or blend trees/spaces with transitions, connections and parameters, as one undoable graph edit.", {"tree": REF, "root_type": enum("state_machine", "blend_tree"), "states": arr(obj({"name": S, "animation": S, "position": V2, "remove": B}, ("name",))), "transitions": arr(obj({"from": S, "to": S, "condition": S, "expression": TEXT, "advance": enum("auto", "enabled", "disabled"), "cross_fade": {"type": "number", "minimum": 0}, "remove": B}, ("from", "to")), 500), "nodes": arr(GRAPH_NODE), "remove_nodes": arr(S), "connections": arr(obj({"to": S, "input": integer(0, 32), "from": S}, ("to", "input", "from"))), "parameters": PROPS, "active": B}, ("tree",)),
    tool("preview_animation", "Interpolate a pose at a time, capture the real editor viewport, and restore values. Method/audio tracks are not executed.", {"player": REF, "name": S, "time": {"type": "number", "minimum": 0}, "capture": B, "viewport": enum("editor_2d", "editor_3d")}, ("player", "name", "time"), read=True),
    tool("get_tilemap", "Read TileMapLayer cells and reusable atlas/tile/terrain identifiers. Reads a bounded region or up to limit used cells.", {"layer": REF, "region": REGION, "limit": integer(1, 10000)}, ("layer",), read=True),
    tool("edit_tileset", "Author atlas tiles, collision polygons and terrain/peering rules on a staged TileSet, then commit with undo.", {"target": RESOURCE, "changes": arr(TS_CHANGE, 500, 1), "scope": enum("node", "shared")}, ("target", "changes")),
    tool("paint_tiles", "Paint cells, regions, patterns or terrain paths and report all actual changes including auto-connected neighbors. Undo restores prior cells.", {"layer": REF, "cells": arr(CELL, 10000), "region": obj({"origin": I2, "size": SIZE, "tile": TILE}, ("origin", "size", "tile")), "pattern": obj({"at": I2, "cells": arr(CELL, 10000, 1)}, ("at", "cells")), "terrain": obj({"set": integer(), "id": integer(-1), "cells": arr(I2, 10000, 1), "mode": enum("connect", "path"), "ignore_empty": B}, ("set", "id", "cells"))}, ("layer",)),
    tool("inspect_runtime", "Read the actual game's scene tree or node properties with run ID and observation time.", {"node": RUN_REF, "properties": arr(S), "depth": integer(0, 10)}, ("node",), read=True),
    tool("capture_viewport", "Return actual PNG pixels plus viewport/capture coordinates. Headless rendering returns an explicit unsupported error.", {"viewport": obj({"kind": enum("game", "editor_2d", "editor_3d"), "run_id": S, "index": integer(0, 3)}, ("kind",)), "rect": obj({"origin": I2, "size": SIZE}, ("origin", "size")), "max_width": integer(1, 4096), "max_height": integer(1, 4096)}, ("viewport",), read=True),
    tool("wait_for_condition", "Observe scene/node/property/signal conditions until satisfied or a bounded timeout; returns last observation.", {"run_id": S, "condition": CONDITION, "timeout_ms": integer(1, 60000), "poll_ms": integer(1, 1000)}, ("run_id", "condition"), read=True),
    tool("get_diagnostics", "Read a fresh snapshot validation of requested sources plus historical editor log entries; unsaved dependencies are included. Snapshot validation excludes caches/symlinks and is limited to 512 MiB and 20,000 files.", {"uris": arr(RES), "revision": S, "run_id": S, "kinds": arr(enum("error", "warning", "log"), 3), "since": integer(), "limit": integer(1, 1000)}, read=True, output=DIAGNOSTICS_OUTPUT),
    tool("sample_performance", "Measure supported Performance monitors over time; include units, sample count and conditions. Unknown metrics are rejected.", {"run_id": S, "duration_ms": integer(1, 60000), "metrics": arr(enum("process_ms", "physics_ms", "fps", "memory_bytes", "objects", "draw_calls", "primitives", "video_memory_bytes"), 8, 1)}, ("run_id", "duration_ms", "metrics"), read=True),
    tool("run_scene", "Start an editor-launched game and wait for the actual runtime helper handshake. Save/restart are explicit (default false).", {"scene": RES, "save": B, "restart": B}),
    tool("stop_game", "Stop the specified run, release injected input, and confirm process termination.", {"run_id": S}, ("run_id",), idempotent=True),
    tool("send_input", "Send timestamped key/mouse/touch/action events through Godot input. Optionally observe a condition and capture afterward. Capture URI enables conversion from image coordinates.", {"run_id": S, "events": arr(INPUT, 1000, 1), "capture_uri": S, "wait_for": CONDITION, "timeout_ms": integer(1, 60000), "capture_after": B, "release_after": B}, ("run_id", "events")),
    tool("inspect_debugger", "Read suspended DAP stack/scopes/variables; frame handles become stale on continue. GDScript is supported.", {"run_id": S, "frame_id": integer(), "pause_id": S, "variables_reference": integer()}, ("run_id",), read=True),
    tool("set_breakpoints", "Add/remove MCP-owned breakpoints while preserving user breakpoints. replace=true replaces only MCP-owned entries.", {"breakpoints": arr(obj({"uri": RES, "line": integer(1, 1_000_000), "enabled": B}, ("uri", "line")), 500), "replace": B}, ("breakpoints",), idempotent=True),
    tool("debug_control", "Pause, continue, step over or step into GDScript. step_out reports unsupported on Godot 4.7.2.", {"run_id": S, "action": enum("pause", "continue", "step_over", "step_into", "step_out"), "pause_id": S}, ("run_id", "action")),
    tool("get_settings", "Read project settings, input mappings and autoloads with property metadata.", {"include": arr(enum("project", "input_actions", "autoload"), 3), "keys": arr(S, 500)}, read=True),
    tool("get_export_presets", "Read actual preset names/platforms and installed export-template readiness.", {"preset": S, "platform": S}, read=True),
    tool("import_assets", "Copy local assets or reimport project assets with options, wait for Godot import, and report resource references and persistence risks.", {"files": arr(obj({"source": FILE, "destination": RES, "options": PROPS, "overwrite": B}, ("destination",)), 500, 1)}, ("files",)),
    tool("move_assets", "Move project files with UID sidecars and reconcile serialized dependencies. Reject unsaved documents and report dynamic references needing review.", {"moves": arr(obj({"from": RES, "to": RES}, ("from", "to")), 200, 1)}, ("moves",)),
    tool("update_settings", "Apply project settings/input actions/autoload changes with undo; save project.godot explicitly to persist.", {"settings": PROPS, "remove": arr(S), "input_actions": arr(obj({"name": S, "events": arr(MAPPING_EVENT, 64), "deadzone": {"type": "number", "minimum": 0, "maximum": 1}, "remove": B}, ("name",))), "autoloads": arr(obj({"name": S, "path": RES, "enabled": B, "remove": B}, ("name",)))}),
    tool("export_build", "Export with a real Godot preset via CLI and verify the output exists. Export success does not imply artifact execution.", {"preset": S, "output": FILE, "debug": B, "timeout_ms": integer(1000, 180000)}, ("preset", "output")),
]
SPECS = {spec["name"]: spec for spec in TOOL_SPECS}
assert len(SPECS) == len(TOOL_SPECS) == 44
