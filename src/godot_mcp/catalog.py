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


def choice(variants: dict, description: str | None = None) -> dict:
    schema = {"type": "object", "properties": variants, "minProperties": 1,
              "maxProperties": 1, "additionalProperties": False}
    if description is not None:
        schema["description"] = description
    return schema


S = {"type": "string", "minLength": 1, "maxLength": 4096}
TEXT = {"type": "string", "maxLength": 1_000_000}
B = {"type": "boolean"}
SAFE_COUNTER = {"type": "integer", "minimum": 0, "maximum": 9_007_199_254_740_991}
PROJECT = {"type": "string", "minLength": 1,
           "description": "Absolute project path; omit after selecting via get_context."}

NULLABLE_STRING = {"type": ["string", "null"]}
DIAGNOSTIC_ENTRY = {"type": "object", "properties": {"kind": enum("error", "warning", "log"), "uri": {"type": "string"}, "line": integer(), "message": TEXT, "cursor": SAFE_COUNTER, "time_usec": SAFE_COUNTER, "count": integer(1)}, "additionalProperties": True}
VALIDATION_SOURCE = {"type": "object", "properties": {"uri": {"type": "string"}, "revision": NULLABLE_STRING, "state": enum("valid", "invalid", "pending", "unavailable"), "valid": {"type": ["boolean", "null"]}, "scope": {"const": "snapshot"}, "entries": arr(DIAGNOSTIC_ENTRY, 2000)}, "required": ["uri", "revision", "state", "valid", "scope", "entries"], "additionalProperties": True}
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
RESOURCE_URI_PROPERTIES = {"uri": {"type": "string", "pattern": r"^(?:res://|godot://resources/).+"}}
RESOURCE_NODE = obj({"scene": RES, "path": NODE_PATH, "property": S}, ("scene", "path", "property"))
RESOURCE = choice({"uri": RESOURCE_URI_PROPERTIES["uri"], "node": RESOURCE_NODE},
                 "Choose exactly one resource selector: uri or node.")
LOCAL_TARGET = RESOURCE_NODE
SCOPED_TARGET = choice({"local": LOCAL_TARGET, "shared": RESOURCE},
                       "Choose exactly one target scope: local node property or shared resource.")
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
CONDITION = choice({
    "scene": obj({"uri": RES}, ("uri",)),
    "node": obj({"node": RUN_REF, "exists": B}, ("node",)),
    "property": obj({"node": RUN_REF, "property": S, "value": VALUE,
                      "operator": enum("eq", "ne", "gt", "gte", "lt", "lte")},
                     ("node", "property", "value")),
    "signal": obj({"node": RUN_REF, "signal": S}, ("node", "signal")),
}, "Choose exactly one condition: scene, node, property, or signal.")
INPUT_COMMON = {"at_ms": {**integer(0, 60_000), "description": "Milliseconds from batch start; events must be nondecreasing."}}
MODIFIERS = {"shift": B, "ctrl": B, "alt": B, "meta": B}
INPUT_EVENT = choice({
    "key": obj({"key": {**S, "description": "Godot key name."},
                 "pressed": {**B, "description": "Whether the key is pressed or released."},
                 "physical": B, **MODIFIERS}, ("key", "pressed")),
    "mouse_button": obj({"button": enum("left", "right", "middle", "wheel_up", "wheel_down"),
                          "position": {**V2, "description": "Pointer position in viewport or capture coordinates."},
                          "pressed": {**B, "description": "Whether the button is pressed or released."}, **MODIFIERS},
                         ("button", "position", "pressed")),
    "mouse_motion": obj({"position": {**V2, "description": "Pointer position in viewport or capture coordinates."},
                          "relative": V2, **MODIFIERS}, ("position",)),
    "touch": obj({"position": {**V2, "description": "Touch position in viewport or capture coordinates."},
                   "pressed": B, "index": integer(0, 15)}, ("position", "pressed")),
    "drag": obj({"position": {**V2, "description": "Touch position in viewport or capture coordinates."},
                  "relative": V2, "index": integer(0, 15)}, ("position", "relative")),
    "action": obj({"action": {**S, "description": "Defined Godot input action name."},
                    "pressed": {**B, "description": "Whether the action is pressed or released."},
                    "strength": {"type": "number", "minimum": 0, "maximum": 1}}, ("action", "pressed")),
}, "Choose exactly one input event kind.")
INPUT = obj({**INPUT_COMMON, "event": INPUT_EVENT}, ("event",))

MAPPING_EVENT = obj({"type": enum("key", "mouse_button", "joypad_button", "joypad_motion"), "key": S,
                     "physical": B, "button": integer(0, 32), "axis": integer(0, 15), "axis_value": N,
                     "shift": B, "ctrl": B, "alt": B, "meta": B}, ("type",))
NODE_SOURCE = choice({"class": {**S, "description": "Node class to instantiate."},
                      "instance": {**RES, "description": "PackedScene URI to instantiate."},
                      "duplicate": {**REF, "description": "Live node reference to duplicate."}},
                     "Choose exactly one node source: class, instance, or duplicate.")
NODE_SPEC = obj({"key": {**S, "description": "Optional unique logical identifier for this record."},
                 "parent_key": {**S, "description": "Optional logical parent key; omitted means the tool parent."},
                 "name": {**S, "description": "Node name."}, "source": NODE_SOURCE, "properties": PROPS},
                ("name", "source"))
SOURCE_RESULT = {"uri": RES, "source": TEXT, "revision": S, "disk_revision": NULLABLE_STRING, "base_disk_revision": NULLABLE_STRING, "baseline_known": B, "conflict": enum("none", "external_change", "baseline_unknown"), "exists_on_disk": B, "unsaved": B, "buffer": S, "external_change": B, "symbols": arr({"type": "object", "additionalProperties": True}, 10000), "range": RANGE}
NORMALIZED_VALIDATION = {"type": "object", "properties": {
    "state": enum("valid", "invalid", "pending", "unavailable"),
    "revision": {**NULLABLE_STRING, "description": "Checked revision when different from the containing document; omitted means that document revision."},
    "checked_state": enum("valid", "invalid"), "scope": {"const": "snapshot"},
    "entries": arr(DIAGNOSTIC_ENTRY, 2000),
}, "required": ["state", "scope"], "additionalProperties": True}
DOCUMENT_SAVE_PROPERTIES = {"state": enum("saved", "failed", "skipped"), "index": integer(),
                            "previous_uri": S, "target": S, "requested": B}
DOCUMENT_SAVE = obj({**DOCUMENT_SAVE_PROPERTIES, "attempts": arr(obj(DOCUMENT_SAVE_PROPERTIES, ("state",)), 200)}, ("state",))
DOCUMENT_RECORD = {"type": "object", "properties": {
    "uri": {"type": "string"}, "state": enum("saved", "modified", "draft", "unavailable"),
    "revision": NULLABLE_STRING, "disk_revision": NULLABLE_STRING, "base_disk_revision": NULLABLE_STRING,
    "baseline_known": B, "conflict": enum("none", "external_change", "baseline_unknown"),
    "effect": enum("created", "updated", "saved"), "applied_revision": S, "validation": NORMALIZED_VALIDATION,
    "save": DOCUMENT_SAVE, "live_reload": enum("succeeded", "failed", "deferred", "not_attempted"),
}, "required": ["uri"], "additionalProperties": True}
RECOVERY = obj({"tool": S, "arguments": {"type": "object", "additionalProperties": True},
                "prerequisite": TEXT}, ("tool", "arguments"))
DOCUMENT_FAILURE = {"type": "object", "properties": {
    "phase": S, "code": S, "message": TEXT, "uri": S, "node": REF, "resource": S,
    "details": {"type": "object", "additionalProperties": True}, "recovery": RECOVERY,
}, "required": ["phase", "code", "message"], "additionalProperties": True}
DOCUMENT_SNAPSHOT = output_schema({
    "status": enum("completed", "partial", "failed"), "complete": B,
    "documents": {"type": "array", "items": DOCUMENT_RECORD}, "failures": arr(DOCUMENT_FAILURE, 1000),
    "undo": UNDO_RESULT, "pending_save": {"type": "array", "items": S}, "pending": arr(S, 200),
    "attachments": arr(obj({"scene": RES, "path": NODE_PATH, "resource": S, "property": S}), 50),
    "validation_snapshot": S, "runtime_application": S, "save_observation": TEXT,
}, ("status", "complete", "documents", "failures", "undo", "pending_save"))

DOCUMENT_RECEIPT_RECORD = obj({
    **{key: DOCUMENT_RECORD["properties"][key] for key in (
        "uri", "state", "revision", "effect", "applied_revision", "conflict",
        "disk_revision", "base_disk_revision", "baseline_known", "live_reload")},
    "validation": obj({key: NORMALIZED_VALIDATION["properties"][key] for key in ("state", "revision", "checked_state")}, ("state",)),
    "save": obj({key: DOCUMENT_SAVE_PROPERTIES[key] for key in ("state", "previous_uri", "target", "requested")}, ("state",)),
}, ("uri",))
DOCUMENT_OUTPUT = output_schema({
    "project": S, "operation_id": S, "status": enum("completed", "partial", "failed"),
    "details_retained": {**B, "description": "The detailed snapshot is currently retained; query get_operation_result before the session or retention window ends."},
    "documents": {"type": "array", "items": DOCUMENT_RECEIPT_RECORD},
    "failures": arr(DOCUMENT_FAILURE, 1000), "pending": arr(S, 200),
    "pending_save": {"type": "array", "items": S},
    "undo": obj({"edit_id": NULLABLE_STRING, "scope": arr(S, 16), "retained_files": arr(S, 200)}),
    "attachments": arr(obj({"scene": RES, "path": NODE_PATH, "resource": S, "property": S}), 50),
}, ("operation_id", "status", "details_retained", "documents"))
DOCUMENT_OUTPUT["oneOf"][0]["additionalProperties"] = False

READ_SCRIPT_OUTPUT = output_schema(SOURCE_RESULT, ("uri", "source", "revision", "symbols"))
DIAGNOSTICS_OUTPUT = output_schema({"entries": arr(DIAGNOSTIC_ENTRY, 1000), "sources": arr(VALIDATION_SOURCE, 200), "entries_are_history": B, "origin": S, "snapshot_id": S, "runtime": {"type": "object", "additionalProperties": True}}, ("entries", "sources", "entries_are_history", "origin"))
OP_FAILURE = obj({"phase": S, "code": S, "message": TEXT, "details": {"type": "object", "additionalProperties": True}}, ("phase", "code", "message", "details"))
OPERATION_RESULT = {"status": enum("completed", "partial", "failed"), "complete": B, "failures": arr(OP_FAILURE, 200), "pending": arr(S, 200)}
SEND_INPUT_OUTPUT = output_schema({**OPERATION_RESULT, "processed": integer(), "elapsed_ms": SAFE_COUNTER, "held_inputs": SAFE_COUNTER, "condition": {"type": "object", "additionalProperties": True}, "capture": {"type": "object", "additionalProperties": True}, "recovery": TEXT, "run_id": S, "observed_at_usec": SAFE_COUNTER, "frame": SAFE_COUNTER}, ("status", "complete", "failures", "pending", "processed", "elapsed_ms", "held_inputs"))
IMPORT_ASSETS_OUTPUT = output_schema({**OPERATION_RESULT, "operation_id": S, "phase": enum("writing", "importing", "reimporting", "settling", "completed", "failed"), "saved": B, "files_written": arr(S, 500), "options_changed": arr(S, 500), "changed_paths": arr(S, 1500), "assets": arr(obj({"uri": RES, "imported": B, "resource": {"anyOf": [obj({"$type": {"const": "Resource"}, "uri": S, "class": S}, ("$type", "uri", "class")), {"type": "null"}]}, "preservation": TEXT}, ("uri", "imported", "resource", "preservation")), 500), "edit_id": NULLABLE_STRING, "undo_state": enum("pending", "available", "unavailable", "not_needed"), "undo": UNDO_RESULT}, ("status", "complete", "failures", "pending", "operation_id", "phase", "saved", "files_written", "options_changed", "changed_paths", "assets", "edit_id", "undo_state", "undo"))
OPERATION_DETAIL_OUTPUT = output_schema({
    "operation_id": S, "tool": S, "editor_epoch": S, "recorded_at_usec": SAFE_COUNTER,
    "snapshot": {"const": True, "description": "Result as recorded at operation time; query live tools for current document state."},
    "pending": B,
    "result": {"anyOf": [DOCUMENT_SNAPSHOT, IMPORT_ASSETS_OUTPUT]},
    "current_undo": obj({"edit_id": NULLABLE_STRING, "available": B, "reason": TEXT}, ("edit_id", "available")),
}, ("operation_id", "tool", "editor_epoch", "recorded_at_usec", "snapshot", "pending", "result", "current_undo"))

SCRIPT_CHANGE = choice({
    "create": obj({"uri": RES, "source": TEXT}, ("uri", "source")),
    "replace": obj({"uri": RES, "if_revision": S, "source": TEXT}, ("uri", "if_revision", "source")),
    "edit": obj({"uri": RES, "if_revision": S,
                  "edits": arr(obj({"range": RANGE, "text": TEXT}, ("range", "text")), 200, 1)},
                 ("uri", "if_revision", "edits")),
}, "Choose exactly one script change: create, replace, or edit.")


TRACK_KEY = choice({
    "set": obj({"time": {"type": "number", "minimum": 0}, "value": VALUE, "transition": N}, ("time", "value")),
    "remove": obj({"time": {"type": "number", "minimum": 0}}, ("time",)),
}, "Choose exactly one key operation: set or remove.")
TRACK = choice({
    "add": obj({"kind": enum("value", "position_3d", "rotation_3d", "scale_3d", "method", "bezier"),
                 "path": S, "keys": arr(TRACK_KEY, 5000), "enabled": B,
                 "interpolation": enum("nearest", "linear", "cubic")}, ("kind", "path")),
    "update": obj({"index": integer(), "path": S, "keys": arr(TRACK_KEY, 5000), "enabled": B,
                    "interpolation": enum("nearest", "linear", "cubic"), "replace_keys": B}, ("index",)),
    "remove": obj({"index": integer()}, ("index",)),
}, "Choose exactly one track operation: add, update, or remove.")
GRAPH_NODE = obj({"name": S, "kind": enum("animation", "blend2", "add2", "blend3", "one_shot", "time_scale", "time_seek", "blend_space_1d", "blend_space_2d"),
                  "animation": S, "position": V2, "min": VALUE, "max": VALUE,
                  "points": arr(obj({"animation": S, "position": VALUE}, ("animation", "position")), 64),
                  "filter": arr(S, 200)}, ("name", "kind"))
SOURCE_REF = choice({"id": integer(0), "key": S}, "Choose exactly one atlas source reference: id or key.")
TILE_DATA_SET = obj({"terrain_set": integer(), "terrain": integer(-1),
                      "peering_bits": {"type": "object", "additionalProperties": integer(-1, 255)},
                      "probability": {"type": "number", "minimum": 0}}, minProperties=1)
TILE_SIZE = {**SIZE, "default": {"x": 16, "y": 16}}
TS_CHANGE = choice({
    "add_atlas": obj({"texture": RES, "key": S, "source_id": integer(0), "tile_size": TILE_SIZE}, ("texture",)),
    "define_tile": obj({"source": SOURCE_REF, "atlas": I2, "size": SIZE, "alternative": integer(), "set": TILE_DATA_SET}, ("source", "atlas")),
    "remove_tile": obj({"source": SOURCE_REF, "atlas": I2, "alternative": integer()}, ("source", "atlas")),
    "add_physics_layer": obj({"collision_layer": integer(), "collision_mask": integer()}),
    "collision": obj({"source": SOURCE_REF, "atlas": I2, "polygons": arr(arr(V2, 100, 3), 32),
                       "alternative": integer(), "physics_layer": integer(0, 31), "one_way": B},
                      ("source", "atlas", "polygons")),
    "add_terrain_set": obj({"mode": enum("corners_and_sides", "corners", "sides"),
                             "terrains": arr(obj({"name": S, "color": VALUE}, ("name",)), 64)}),
    "terrain": obj({"source": SOURCE_REF, "atlas": I2, "set": TILE_DATA_SET, "alternative": integer()},
                    ("source", "atlas", "set")),
}, "Choose exactly one TileSet change operation.")


def tool(name, description, properties, required=(), *, read=False, destructive=False, idempotent=False, constraints=None, output=None):
    schema = obj({"project": PROJECT, **properties}, required, **(constraints or {}))
    result = {"name": name, "description": description, "inputSchema": schema,
            "annotations": {"readOnlyHint": read, "destructiveHint": destructive,
                            "idempotentHint": idempotent, "openWorldHint": False}}
    if output is not None:
        result["outputSchema"] = output
    return result


TOOL_SPECS = [
    tool("install_plugin", "Install and enable the bundled plugin in an existing Godot project before connecting to the editor. Close the project in Godot first. Creates a rollback backup and registers project discovery.", {"project": {**S, "description": "Required absolute path to the directory containing project.godot."}}, ("project",)),
    tool("get_context", "Read project/engine/product/protocol versions, active scene, selection, unsaved documents, pending operation IDs and actual run state.", {"scope": enum("all", "project", "editor", "runtime")}, read=True),
    tool("get_operation_result", "Read the retained detailed result of a document mutation or import without repeating it. Results are operation-time snapshots; current_undo reports current eligibility separately. The editor session retains at most 64 records and 16 MiB of serialized results, evicting completed records first. Expired, unknown, or oversized pending records return explicit errors.", {"operation_id": S}, ("operation_id",), read=True, output=OPERATION_DETAIL_OUTPUT),
    tool("find_assets", "Search filenames, source text or symbols. Returns reusable res:// URIs and one-based source locations.", {"query": S, "mode": enum("name", "text", "symbol"), "types": arr(S, 32), "scope": {"type": "string", "pattern": "^res://"}, "limit": integer(1, 500)}, ("query",), read=True),
    tool("get_class_info", "Inspect actual engine or project script classes, properties, methods and signals; optionally filter a member.", {"class": S, "member": S}, ("class",), read=True),
    tool("get_scene", "Inspect live scene nodes, unsaved values, connections, inheritance overrides and actual Control layout.", {"scene": RES, "path": NODE_PATH, "properties": {**arr(S), "description": "Property names: omitted means all editor properties when properties is included; [] means none."}, "include": {**arr(enum("properties", "overrides", "connections", "layout"), 4), "description": "Sections to include; omitted means structure only."}, "depth": integer(0, 32)}, read=True),
    tool("open_scene", "Open and activate a saved scene in the editor.", {"scene": RES}, ("scene",), idempotent=True),
    tool("create_scene", "Create a scene with a typed root or inherited source. Saves the new file and returns its root reference.", {"uri": RES, "root_class": S, "root_name": S, "inherits": RES}, ("uri", "root_name")),
    tool("create_nodes", "Create a flat related-node batch. Each node requires name and exactly one source choice: class, instance, or duplicate; parent_key links nodes within the batch. Returns actual names and references.", {"parent": REF, "nodes": arr(NODE_SPEC, 1000, 1)}, ("parent", "nodes")),
    tool("update_nodes", "Batch node properties, names and reparenting in one scene. Use references in the source scene to edit the original. Container-controlled layout is reported.", {"changes": arr(obj({"node": REF, "set": PROPS, "name": S, "parent": REF, "index": integer(0, 10000), "keep_global_transform": B}, ("node",)), 200, 1)}, ("changes",)),
    tool("delete_nodes", "Delete related nodes with undo; report affected persistent connections and NodePath references. Reject inherited members and overlapping selections.", {"nodes": arr(REF, 200, 1)}, ("nodes",), destructive=True),
    tool("save_documents", "Save requested documents; Godot scene saves may also persist linked resources. Reports observed extra source saves, partial failures, and the separate undo boundary.", {"uris": arr({"type": "string", "pattern": "^(res://|godot://resources/).+"}, 200, 1), "save_as": {"type": "object", "additionalProperties": RES}}, ("uris",), idempotent=True, output=DOCUMENT_OUTPUT),
    tool("undo_edit", "Undo the latest MCP edit if its editor history has not changed since. Filesystem operations report their separate rollback scope.", {"edit_id": S}, ("edit_id",), destructive=True),
    tool("get_resource", "Read a resource selected by uri or by node scene/path/property, including nested references, known users and import provenance. Sharing scan covers open scenes and indexed project dependencies.", {"target": RESOURCE, "properties": arr(S), "depth": integer(0, 5)}, ("target",), read=True),
    tool("create_resource", "Create an in-memory resource, optionally attach it or save it. Returns a reusable resource URI.", {"class": S, "properties": PROPS, "assign_to": obj({"node": REF, "property": S}, ("node", "property")), "save_as": RES}, ("class",)),
    tool("update_resource", "Change a resource with an explicit local or shared target. Imported shared sources require detaching to an authored resource.", {"target": SCOPED_TARGET, "set": PROPS, "save_as": RES}, ("target", "set")),
    tool("read_script", "Read the current source, including unsaved editor/store changes, with its revision and symbols. Ranges use one-based Unicode columns and exclusive ends.", {"uri": RES, "symbol": S, "range": RANGE}, ("uri",), read=True, output=READ_SCRIPT_OUTPUT),
    tool("create_script", "Create and save the source before validation. If attachment fails, the source remains saved. Repair source with edit_script, then retry node script attachment with update_nodes (script property) or shader attachment with update_resource (ShaderMaterial shader property).", {"uri": RES, "source": TEXT, "attach_to": arr(REF, 50), "material": RESOURCE}, ("uri", "source"), output=DOCUMENT_OUTPUT),
    tool("edit_script", "Apply a complete source replacement or one or more range edits at an exact revision; changes remain live even when compilation fails. The change selects exactly one replace or edit payload. Save explicitly to persist.", {"change": choice({"replace": obj({"uri": RES, "if_revision": S, "source": TEXT}, ("uri", "if_revision", "source")), "edit": obj({"uri": RES, "if_revision": S, "edits": arr(obj({"range": RANGE, "text": TEXT}, ("range", "text")), 200, 1)}, ("uri", "if_revision", "edits"))}, "Choose exactly one script edit: replace or edit.")}, ("change",), output=DOCUMENT_OUTPUT),
    tool("apply_script_changes", "Apply a bounded batch of live source changes; save=true persists the batch afterward. Changes remain live on compile failure, attachments are outside this batch, and game hot reload is not promised. Validation snapshots exclude caches/symlinks and are limited to 512 MiB and 20,000 files.", {"changes": arr(SCRIPT_CHANGE, 100, 1), "save": {"type": "boolean", "default": False, "description": "Persist the whole batch after application; false leaves live drafts."}}, ("changes",), output=DOCUMENT_OUTPUT),
    tool("update_signals", "Connect/disconnect persistent signal handlers with optional binds in one scene. Missing handler code is reported.", {"connect": arr(SIGNAL), "disconnect": arr(SIGNAL)}, idempotent=True),
    tool("get_animation", "Inspect animation tracks/keys or AnimationTree states, transitions, blend connections and parameter values.", {"node": REF, "animation": S}, ("node",), read=True),
    tool("edit_animation", "Create or edit an AnimationPlayer animation and typed tracks/keys. Local scope isolates a player's shared library; shared scope is explicit.", {"player": REF, "name": S, "create": B, "length": {"type": "number", "exclusiveMinimum": 0}, "loop": B, "tracks": arr(TRACK), "scope": enum("local", "shared")}, ("player", "name")),
    tool("edit_animation_graph", "Build state machines or blend trees/spaces with transitions, connections and parameters, as one undoable graph edit.", {"tree": REF, "root_type": enum("state_machine", "blend_tree"), "states": arr(obj({"name": S, "animation": S, "position": V2, "remove": B}, ("name",))), "transitions": arr(obj({"from": S, "to": S, "condition": S, "expression": TEXT, "advance": enum("auto", "enabled", "disabled"), "cross_fade": {"type": "number", "minimum": 0}, "remove": B}, ("from", "to")), 500), "nodes": arr(GRAPH_NODE), "remove_nodes": arr(S), "connections": arr(obj({"to": S, "input": integer(0, 32), "from": S}, ("to", "input", "from"))), "parameters": PROPS, "active": B}, ("tree",)),
    tool("preview_animation", "Interpolate a pose at a time, capture the real editor viewport, and restore values. Method/audio tracks are not executed.", {"player": REF, "name": S, "time": {"type": "number", "minimum": 0}, "capture": B, "viewport": enum("editor_2d", "editor_3d")}, ("player", "name", "time"), read=True),
    tool("get_tilemap", "Read TileMapLayer cells and reusable atlas/tile/terrain identifiers. Reads a bounded region or up to limit used cells.", {"layer": REF, "region": REGION, "limit": integer(1, 10000)}, ("layer",), read=True),
    tool("edit_tileset", "Batch atlas, collision and terrain edits on a staged TileSet with one undo. Choose a local node property or shared resource target explicitly.", {"target": SCOPED_TARGET, "changes": arr(TS_CHANGE, 500, 1)}, ("target", "changes")),
    tool("paint_tiles", "Paint cells, regions, patterns or terrain paths and report all actual changes including auto-connected neighbors. Undo restores prior cells.", {"layer": REF, "cells": arr(CELL, 10000), "region": obj({"origin": I2, "size": SIZE, "tile": TILE}, ("origin", "size", "tile")), "pattern": obj({"at": I2, "cells": arr(CELL, 10000, 1)}, ("at", "cells")), "terrain": obj({"set": integer(), "id": integer(-1), "cells": arr(I2, 10000, 1), "mode": enum("connect", "path"), "ignore_empty": B}, ("set", "id", "cells"))}, ("layer",)),
    tool("inspect_runtime", "Read the actual game's scene tree or node properties with run ID and observation time.", {"node": RUN_REF, "properties": arr(S), "depth": integer(0, 10)}, ("node",), read=True),
    tool("capture_viewport", "Return actual PNG pixels plus viewport/capture coordinates. Headless rendering returns an explicit unsupported error.", {"viewport": obj({"kind": enum("game", "editor_2d", "editor_3d"), "run_id": S, "index": integer(0, 3)}, ("kind",)), "rect": obj({"origin": I2, "size": SIZE}, ("origin", "size")), "max_width": integer(1, 4096), "max_height": integer(1, 4096)}, ("viewport",), read=True),
    tool("wait_for_condition", "Observe scene/node/property/signal conditions until satisfied or a bounded timeout; returns last observation.", {"run_id": S, "condition": CONDITION, "timeout_ms": integer(1, 60000), "poll_ms": integer(1, 1000)}, ("run_id", "condition"), read=True),
    tool("get_diagnostics", "Read a fresh snapshot validation of requested sources plus historical editor log entries; unsaved dependencies are included. Snapshot validation excludes caches/symlinks and is limited to 512 MiB and 20,000 files.", {"uris": arr(RES), "revision": S, "run_id": S, "kinds": arr(enum("error", "warning", "log"), 3), "since": SAFE_COUNTER, "limit": integer(1, 1000)}, read=True, output=DIAGNOSTICS_OUTPUT),
    tool("sample_performance", "Measure supported Performance monitors over time; include units, sample count and conditions. Unknown metrics are rejected.", {"run_id": S, "duration_ms": integer(1, 60000), "metrics": arr(enum("process_ms", "physics_ms", "fps", "memory_bytes", "objects", "draw_calls", "primitives", "video_memory_bytes"), 8, 1)}, ("run_id", "duration_ms", "metrics"), read=True),
    tool("run_scene", "Start an editor-launched game and wait for the actual runtime helper handshake. Save/restart are explicit (default false).", {"scene": RES, "save": B, "restart": B}),
    tool("stop_game", "Stop the specified run, release injected input, and confirm process termination.", {"run_id": S}, ("run_id",), idempotent=True),
    tool("send_input", "Send timestamped key/mouse/touch/action events through Godot input; each event selects exactly one named kind payload. Capture position and relative coordinates use capture pixels. Timeouts retain applied effects; retry failed observation or capture rather than repeating the mutation.", {"run_id": S, "events": arr(INPUT, 1000, 1), "capture_uri": S, "wait_for": CONDITION, "timeout_ms": integer(1, 60000), "capture_after": B, "release_after": B}, ("run_id", "events"), output=SEND_INPUT_OUTPUT),
    tool("inspect_debugger", "Read suspended DAP stack/scopes/variables; frame handles become stale on continue. GDScript is supported.", {"run_id": S, "frame_id": integer(), "pause_id": S, "variables_reference": integer()}, ("run_id",), read=True),
    tool("set_breakpoints", "Add/remove MCP-owned breakpoints while preserving user breakpoints. replace=true replaces only MCP-owned entries.", {"breakpoints": arr(obj({"uri": RES, "line": integer(1, 1_000_000), "enabled": B}, ("uri", "line")), 500), "replace": B}, ("breakpoints",), idempotent=True),
    tool("debug_control", "Pause, continue, step over or step into GDScript. step_out reports unsupported on Godot 4.7.2.", {"run_id": S, "action": enum("pause", "continue", "step_over", "step_into", "step_out"), "pause_id": S}, ("run_id", "action")),
    tool("get_settings", "Read project settings, input mappings and autoloads with property metadata.", {"include": arr(enum("project", "input_actions", "autoload"), 3), "keys": arr(S, 500)}, read=True),
    tool("get_export_presets", "Read actual preset names/platforms and installed export-template readiness.", {"preset": S, "platform": S}, read=True),
    tool("import_assets", "Copy local assets or reimport project assets with options. Timeouts retain applied effects and return an operation ID; query the operation rather than repeating the mutation.", {"files": arr(obj({"source": FILE, "destination": RES, "options": PROPS, "overwrite": B}, ("destination",)), 500, 1)}, ("files",), output=IMPORT_ASSETS_OUTPUT),
    tool("move_assets", "Move project files with UID sidecars and reconcile serialized dependencies. Reject unsaved documents and report dynamic references needing review.", {"moves": arr(obj({"from": RES, "to": RES}, ("from", "to")), 200, 1)}, ("moves",)),
    tool("update_settings", "Apply project settings/input actions/autoload changes with undo; save project.godot explicitly to persist.", {"settings": PROPS, "remove": arr(S), "input_actions": arr(obj({"name": S, "events": arr(MAPPING_EVENT, 64), "deadzone": {"type": "number", "minimum": 0, "maximum": 1}, "remove": B}, ("name",))), "autoloads": arr(obj({"name": S, "path": RES, "enabled": B, "remove": B}, ("name",)))}),
    tool("export_build", "Export with a real Godot preset via CLI and verify the output exists. Export success does not imply artifact execution.", {"preset": S, "output": FILE, "debug": B, "timeout_ms": integer(1000, 180000)}, ("preset", "output")),
]
# Canonical input contracts and published tool schemas are the same definitions.
DOCUMENT_TOOLS = {"create_script", "edit_script", "apply_script_changes", "save_documents"}
SPECS = {spec["name"]: spec for spec in TOOL_SPECS}
assert len(SPECS) == len(TOOL_SPECS) == 45
