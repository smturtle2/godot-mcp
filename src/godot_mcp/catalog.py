"""Executable tool contracts shared by the MCP server, tests, and docs generator."""
from __future__ import annotations

from .guide import GUIDE_SECTIONS


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
V3 = obj({"x": N, "y": N, "z": N}, ("x", "y", "z"))
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
REVISIONS = {"type": "object", "propertyNames": RES, "maxProperties": 100,
             "additionalProperties": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}
SOURCE_RESULT = {"uri": RES, "source": TEXT, "revision": S, "disk_revision": NULLABLE_STRING, "base_disk_revision": NULLABLE_STRING, "baseline_known": B, "conflict": enum("none", "external_change", "baseline_unknown"), "exists_on_disk": B, "unsaved": B, "buffer": S, "external_change": B, "base_retained": B, "symbols": arr({"type": "object", "additionalProperties": True}, 10000), "symbols_truncated": B, "range": RANGE}
SOURCE_PROVENANCE = obj({
    "run_id": TEXT, "running": B, "state": enum("not_running", "unverified", "matches_startup", "source_changed"),
    "startup_files": enum("unverified", "matched", "mismatched", "unavailable"),
    "behavior": {"const": "unverified", "description": "File identity never proves behavior; assess the requested runtime observation separately."},
    "scope": TEXT, "source_snapshot_id": S, "changed_uris": arr(RES, 20000), "unclassified_uris": arr(RES, 20000),
    "startup_changed_uris": arr(RES, 20000), "launch_changed_uris": arr(RES, 20000), "restart_required": {"type": ["boolean", "null"]}, "evidence": TEXT,
    "runtime_impact": enum("unknown", "not_observed", "confirmed"), "runtime_script_changes": arr(RES, 20000),
    "observed_runtime": B, "observation_error": {"type": "object", "additionalProperties": True},
}, ("run_id", "running", "state", "startup_files", "behavior", "scope"))
RUN_OUTPUT = output_schema({"run_id": S, "scene": RES, "running": B, "runtime_connected": B,
                            "runtime": {"type": "object", "additionalProperties": True}, "source_provenance": SOURCE_PROVENANCE},
                           ("run_id", "scene", "running", "runtime_connected", "source_provenance"))
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
STATE_SUMMARY = obj({key: S for key in ("applied", "saved", "editor_reload", "diagnostics", "runtime")})
DOCUMENT_SNAPSHOT = output_schema({
    "state_summary": STATE_SUMMARY,
    "status": enum("pending", "completed", "partial", "failed"), "complete": B,
    "documents": {"type": "array", "items": DOCUMENT_RECORD}, "failures": arr(DOCUMENT_FAILURE, 1000),
    "undo": UNDO_RESULT, "pending_save": {"type": "array", "items": S}, "pending": arr(S, 200),
    "attachments": arr({"type": "object", "additionalProperties": True}, 100),
    "validation_snapshot": S, "runtime_application": S, "save_observation": TEXT,
}, ("status", "complete", "documents", "failures", "undo", "pending_save"))

DOCUMENT_RECEIPT_RECORD = obj({
    **{key: DOCUMENT_RECORD["properties"][key] for key in (
        "uri", "state", "revision", "effect", "applied_revision", "conflict",
        "disk_revision", "base_disk_revision", "baseline_known", "live_reload")},
    "validation": obj({key: NORMALIZED_VALIDATION["properties"][key] for key in ("state", "revision", "checked_state")}, ("state",)),
    "save": obj({key: DOCUMENT_SAVE_PROPERTIES[key] for key in ("state", "previous_uri", "target", "requested")}, ("state",)),
    "merged": B,
    "editor_events": {"type": "object", "additionalProperties": True},
    "save_receipt": {"type": "object", "additionalProperties": True},
}, ("uri",))
DOCUMENT_OUTPUT = output_schema({
    "state_summary": STATE_SUMMARY,
    "project": S, "operation_id": S, "status": enum("pending", "completed", "partial", "failed"),
    "details_retained": {**B, "description": "The detailed snapshot is currently retained; query get_operation_result before the session or retention window ends."},
    "documents": {"type": "array", "items": DOCUMENT_RECEIPT_RECORD},
    "failures": arr(DOCUMENT_FAILURE, 1000), "pending": arr(S, 200),
    "pending_save": {"type": "array", "items": S},
    "undo": obj({"edit_id": NULLABLE_STRING, "scope": arr(S, 16), "retained_files": arr(S, 200),
                 "steps": arr(obj({"edit_id": S, "scope": S}, ("edit_id", "scope")), 200)}),
    "attachments": arr({"type": "object", "additionalProperties": True}, 100),
    "connections": arr({"type": "object", "additionalProperties": True}, 100),
    "phase": S, "phases": {"type": "object", "additionalProperties": S}, "resumable": B,
    "runtime": SOURCE_PROVENANCE, "validation_snapshot": S,
    "result_query_error": obj({"code": S, "message": TEXT}, ("code", "message")),
    "editor_events": {"type": "object", "additionalProperties": True},
    "save_receipt": {"type": "object", "additionalProperties": True},
}, ("operation_id", "status", "details_retained", "documents"))
DOCUMENT_OUTPUT["oneOf"][0]["additionalProperties"] = False

READ_SCRIPTS_OUTPUT = output_schema({"documents": arr(obj(SOURCE_RESULT, ("uri", "source", "revision", "symbols", "base_retained")), 100), "base_revisions": REVISIONS, "editor_epoch": S}, ("documents", "base_revisions", "editor_epoch"))
DIAGNOSTICS_OUTPUT = output_schema({"operation_id": S, "status": enum("pending", "completed"), "details_retained": B, "sources": arr(VALIDATION_SOURCE, 200), "basis": {"const": "snapshot"}, "state": enum("valid", "invalid", "pending", "unavailable"), "scope": enum("requested_sources", "project_sources"), "coverage": {"type": "object", "additionalProperties": True}, "snapshot_id": S, "observed_errors": integer(), "observed_warnings": integer(), "error_count": integer(), "warning_count": integer(), "reason": S}, ("sources", "basis", "state", "scope", "coverage"))
LOGS_OUTPUT = output_schema({"entries": arr(DIAGNOSTIC_ENTRY, 1000), "history": {"const": True}, "current_verdict": {"const": False}, "origin": enum("editor", "runtime"), "run_id": S}, ("entries", "history", "current_verdict", "origin"))
OP_FAILURE = obj({"phase": S, "code": S, "message": TEXT, "details": {"type": "object", "additionalProperties": True}}, ("phase", "code", "message", "details"))
OPERATION_RESULT = {"status": enum("completed", "partial", "failed"), "complete": B, "failures": arr(OP_FAILURE, 200), "pending": arr(S, 200)}
GENERIC_OBJECT = {"type": "object", "additionalProperties": True}
ASSET_OPERATION = {
    "type": "object", "properties": {
        "operation_id": S, "status": enum("pending", "completed", "partial", "failed"), "complete": B,
        "pending": arr(S, 20000), "failures": arr(OP_FAILURE, 20000), "applied": arr(S, 20000),
        "remaining": arr(S, 20000), "edit_id": NULLABLE_STRING,
        "editor_sync": enum("pending", "completed", "not_needed", "failed"),
        "deletion_id": S, "deletion_ids": arr(S, 20000), "mode": enum("recoverable", "permanent"),
        "remaining_references": arr(GENERIC_OBJECT, 20000), "undo_state": enum("available", "unavailable"),
        "recovery": GENERIC_OBJECT,
    }, "required": ["operation_id", "status", "complete", "pending", "failures", "applied",
                      "remaining", "edit_id", "editor_sync"], "additionalProperties": True,
}
ASSET_PREVIEW = {
    "type": "object", "properties": {
        "preview": {"const": True}, "plan_id": S, "tool": S, "can_apply": B,
        "targets": arr(GENERIC_OBJECT, 20000), "references": arr(GENERIC_OBJECT, 20000),
        "blockers": arr(GENERIC_OBJECT, 20000), "coverage": GENERIC_OBJECT,
        "mode": enum("recoverable", "permanent"), "editor_epoch": S,
    }, "required": ["preview", "plan_id", "tool", "can_apply", "targets", "references", "blockers", "coverage"],
    "additionalProperties": True,
}
ASSET_OUTPUT = {"type": "object", "oneOf": [ASSET_PREVIEW, ASSET_OPERATION, ERROR_RESULT]}
ASSET_OPERATION_OUTPUT = {"type": "object", "oneOf": [ASSET_OPERATION, ERROR_RESULT]}
INPUT_STAMP = obj({"injected_at_usec": SAFE_COUNTER, "frame": SAFE_COUNTER})
PROPERTY_OBSERVATION = obj({"node": RUN_REF, "exists": B, "properties": PROPS,
                            "unavailable_properties": arr(S, 32), "observed_at_usec": SAFE_COUNTER, "frame": SAFE_COUNTER})
SEND_INPUT_OUTPUT = output_schema({**OPERATION_RESULT,
    "injections": arr(obj({**INPUT_STAMP["properties"], "index": integer(), "at_ms": integer(0, 60000)}), 1000),
    "release": obj({**INPUT_STAMP["properties"], "count": integer()}),
    "observations": obj({"before": arr(PROPERTY_OBSERVATION, 32), "after": arr(PROPERTY_OBSERVATION, 32)}), "processed": integer(), "elapsed_ms": SAFE_COUNTER, "held_inputs": SAFE_COUNTER, "condition": {"type": "object", "additionalProperties": True}, "capture": {"type": "object", "additionalProperties": True}, "recovery": TEXT, "run_id": S, "observed_at_usec": SAFE_COUNTER, "frame": SAFE_COUNTER}, ("status", "complete", "failures", "pending", "processed", "elapsed_ms", "held_inputs"))
IMPORT_ASSETS_OUTPUT = output_schema({**OPERATION_RESULT, "operation_id": S, "phase": enum("writing", "importing", "reimporting", "settling", "completed", "failed"), "saved": B, "files_written": arr(S, 500), "options_changed": arr(S, 500), "changed_paths": arr(S, 1500), "assets": arr(obj({"uri": RES, "imported": B, "resource": {"anyOf": [obj({"$type": {"const": "Resource"}, "uri": S, "class": S}, ("$type", "uri", "class")), {"type": "null"}]}, "preservation": TEXT}, ("uri", "imported", "resource", "preservation")), 500), "edit_id": NULLABLE_STRING, "undo_state": enum("pending", "available", "unavailable", "not_needed"), "undo": UNDO_RESULT}, ("status", "complete", "failures", "pending", "operation_id", "phase", "saved", "files_written", "options_changed", "changed_paths", "assets", "edit_id", "undo_state", "undo"))
OPERATION_DETAIL_OUTPUT = output_schema({
    "operation_id": S, "tool": S, "editor_epoch": S, "recorded_at_usec": SAFE_COUNTER,
    "snapshot": {"const": True, "description": "Result as recorded at operation time; query live tools for current document state."},
    "pending": B,
    "result": {"anyOf": [DOCUMENT_SNAPSHOT, IMPORT_ASSETS_OUTPUT, DIAGNOSTICS_OUTPUT, ASSET_OPERATION]},
    "current_runtime": SOURCE_PROVENANCE,
    "current_resume": obj({"available": B, "running": B, "reason": TEXT}, ("available",)),
    "current_undo": obj({"edit_id": NULLABLE_STRING, "available": B, "reason": TEXT}, ("edit_id", "available")),
}, ("operation_id", "tool", "editor_epoch", "recorded_at_usec", "snapshot", "pending", "result", "current_undo"))

SOURCE_ATTACHMENT = choice({
    "script": obj({"uri": RES, "node": REF}, ("uri", "node")),
    "shader": obj({"uri": RES, "target": SCOPED_TARGET}, ("uri", "target")),
}, "Attach one source from the patch: a script to a node, or a shader to an explicitly scoped ShaderMaterial.")
SOURCE_CONNECTIONS = obj({"connect": arr(SIGNAL, 100), "disconnect": arr(SIGNAL, 100)})
PATCH_OUTPUT = {"type": "object", "oneOf": [
    *DOCUMENT_OUTPUT["oneOf"],
    obj({"preview": {"const": True}, "documents": arr(obj({"uri": RES, "effect": enum("created", "updated"),
          "revision": S, "current_revision": NULLABLE_STRING, "merged": B, "source": TEXT},
          ("uri", "effect", "revision", "current_revision", "merged", "source")), 100),
         "save_plan": {"type": "object", "additionalProperties": True}, "attachments": arr(SOURCE_ATTACHMENT, 100),
         "connections": SOURCE_CONNECTIONS, "validation": {"const": "not_run"}, "editor_epoch": S, "project": S},
        ("preview", "documents", "save_plan", "attachments", "connections", "validation", "editor_epoch")),
]}


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


def tool(name, description, properties, required=(), *, read=False, destructive=False, idempotent=False, constraints=None, output=None, project_bound=True):
    schema = obj({**({"project": PROJECT} if project_bound else {}), **properties}, required, **(constraints or {}))
    result = {"name": name, "description": description, "inputSchema": schema,
            "annotations": {"readOnlyHint": read, "destructiveHint": destructive,
                            "idempotentHint": idempotent, "openWorldHint": False}}
    if output is not None:
        result["outputSchema"] = output
    return result


TOOL_SPECS = [
    tool("get_guide", "Read the Godot MCP manual. Omit section to get the index; select a section to read its English content.", {"section": {**enum(*GUIDE_SECTIONS), "description": "Manual section to read. Omit to read the index."}, "tool": {**S, "description": "One published tool name; requires section=tools."}}, read=True, idempotent=True, project_bound=False),
    tool("create_project", "Create an empty project, install the plugin, open Godot and connect. Retries resume this tool’s recorded setup without replacing project settings.", {"project": {**S, "description": "Absolute path to a new or empty project directory."}, "name": {**S, "description": "Project name; defaults to the folder name."}, "editor": {**S, "description": "Godot executable; defaults to GODOT or godot/godot4 on PATH."}}, ("project",), project_bound=False),
    tool("install_plugin", "Install and enable the bundled plugin in an existing Godot project before connecting to the editor. Close the project in Godot first. Creates a rollback backup and registers project discovery.", {"project": {**S, "description": "Required absolute path to the directory containing project.godot."}}, ("project",)),
    tool("get_context", "Read versions, active scene, selection, unsaved documents, pending operations, run state and durable deletion records for restore or purge. Use scope=progress for a compact operation status; set runtime_details=true to request fresh runtime source provenance.", {"scope": enum("all", "project", "editor", "runtime", "progress"), "runtime_details": B}, read=True),
    tool("get_operation_result", "Read retained results without repeating work; wait_ms optionally waits for running work. Snapshots preserve operation-time facts; current_undo/current_resume report live eligibility. The editor retains 64 results/16 MiB per session, evicting completed records first.", {"operation_id": S, "wait_ms": integer(0, 60000)}, ("operation_id",), read=True, output=OPERATION_DETAIL_OUTPUT),
    tool("find_assets", "Search paths, live source text or symbols, including never-saved drafts, or list files, directories and live source drafts. Name, content and symbol modes require a nonempty query and use case-insensitive substring matching; list ignores query. Listing excludes dot paths and symlinks, reuses project bounds and skipped-path reporting, and recursive controls directory traversal (default true). Source matches include their read revision; pagination observes current state.", {"query": {**S, "description": "Required and nonempty for name, content and symbol modes; ignored by list."}, "mode": {**enum("name", "content", "symbol", "list"), "default": "name"}, "recursive": {**B, "default": True, "description": "List mode only: include nested directories and files when true; default true."}, "types": arr(S, 32), "scope": {"type": "string", "pattern": "^res://"}, "limit": integer(1, 1000), "offset": integer(0, 1000000)}, (), read=True),
    tool("delete_assets", "Preview or delete assets and their companions. Preview locks the selected mode, reference policy and current revisions; a stale plan must be previewed again. allow_broken reports references that will remain broken. permanent deletion is irreversible; recoverable backups survive editor restarts and can be inspected with Undo/get_operation_result.", {"action": choice({
        "preview": obj({"paths": arr(RES, 200, 1), "mode": {**enum("recoverable", "permanent"), "default": "recoverable"}, "references": {**enum("block", "allow_broken"), "default": "block"}, "include_unsaved": {**arr(RES, 200), "description": "Explicitly authorize removal of targeted unsaved gd/gdshader buffers or drafts."}}, ("paths",)),
        "apply": obj({"plan_id": S}, ("plan_id",)),
    }, "Choose exactly one asset deletion action: preview or apply." )}, ("action",), destructive=True, output=ASSET_OUTPUT),
    tool("purge_deleted_assets", "Preview or permanently purge recoverable asset backups by deletion ID. Preview locks the selected IDs and revisions; a stale plan must be previewed again. Purging invalidates restore for those backups and cannot be undone.", {"action": choice({
        "preview": obj({"deletion_ids": arr(S, 200, 1)}, ("deletion_ids",)),
        "apply": obj({"plan_id": S}, ("plan_id",)),
    }, "Choose exactly one backup purge action: preview or apply.")}, ("action",), destructive=True, output=ASSET_OUTPUT),
    tool("restore_assets", "Restore a recoverable deletion by deletion ID. Optional paths select a subset of backed up entries and expand folders and companion files. The operation reports editor synchronization and can be followed with Undo/get_operation_result.", {"deletion_id": S, "paths": arr(RES, 200, 1)}, ("deletion_id",), output=ASSET_OPERATION_OUTPUT),
    tool("get_class_info", "Inspect actual engine or project script classes, properties, methods and signals; optionally filter a member.", {"class": S, "member": S}, ("class",), read=True),
    tool("get_scene", "Inspect live scene nodes, unsaved values, connections, inheritance overrides and actual Control layout.", {"scene": RES, "path": NODE_PATH, "properties": {**arr(S), "description": "Property names: omitted means all editor properties when properties is included; [] means none."}, "include": {**arr(enum("properties", "overrides", "connections", "layout"), 4), "description": "Sections to include; omitted means structure only."}, "depth": integer(0, 32)}, read=True),
    tool("open_scene", "Open and activate a saved scene in the editor.", {"scene": RES}, ("scene",), idempotent=True),
    tool("create_scene", "Create a scene with a typed root or inherited source. Saves the new file and returns its root reference.", {"uri": RES, "root_class": S, "root_name": S, "inherits": RES}, ("uri", "root_name")),
    tool("create_nodes", "Create a flat related-node batch. Each node requires name and exactly one source choice: class, instance, or duplicate; parent_key links nodes within the batch. Returns actual names and references.", {"parent": REF, "nodes": arr(NODE_SPEC, 1000, 1)}, ("parent", "nodes")),
    tool("update_nodes", "Batch node properties, names and reparenting in one scene. Use references in the source scene to edit the original. Container-controlled layout is reported.", {"changes": arr(obj({"node": REF, "set": PROPS, "name": S, "parent": REF, "index": integer(0, 10000), "keep_global_transform": B}, ("node",)), 200, 1)}, ("changes",)),
    tool("delete_nodes", "Delete related nodes with undo; report affected persistent connections and NodePath references. Reject inherited members and overlapping selections.", {"nodes": arr(REF, 200, 1)}, ("nodes",), destructive=True),
    tool("save_documents", "Persist the listed authored documents. Imported resources are managed by import; use save_as to export an authored copy. A scene save that could save other edited authored documents first returns SAVE_SCOPE_REQUIRED with their paths. Saving and source validation are independent; editor Undo does not restore saved disk files.", {"uris": arr({"type": "string", "pattern": "^(res://|godot://resources/).+"}, 200, 1), "save_as": {"type": "object", "additionalProperties": RES}}, ("uris",), idempotent=True, output=DOCUMENT_OUTPUT),
    tool("undo_edit", "Undo the latest MCP edit if its history and state guards still match. Recoverable asset deletion restores stored files and may return an operation_id while the editor scans; permanent deletion and purged recovery have no Undo.", {"edit_id": S}, ("edit_id",), destructive=True),
    tool("get_resource", "Read a resource selected by uri or by node scene/path/property, including nested references, known users and import provenance. Sharing scan covers open scenes and indexed project dependencies.", {"target": RESOURCE, "properties": arr(S), "depth": integer(0, 5)}, ("target",), read=True),
    tool("create_resource", "Create an in-memory resource, optionally attach it or save it. Returns a reusable resource URI.", {"class": S, "properties": PROPS, "assign_to": obj({"node": REF, "property": S}, ("node", "property")), "save_as": RES}, ("class",)),
    tool("update_resource", "Change a resource with an explicit local or shared target. Imported shared sources require detaching to an authored resource.", {"target": SCOPED_TARGET, "set": PROPS, "save_as": RES}, ("target", "set")),
    tool("read_scripts", "Read one or more current editor sources/drafts, their revisions and symbols. Pass updated paths' base_revisions to apply_script_changes. Ranges use one-based Unicode columns and exclusive ends. Read bases are retained for three-way merge within 256 versions/16 MiB per editor session.", {"documents": arr(obj({"uri": RES, "range": RANGE, "symbol": S}, ("uri",)), 100, 1)}, ("documents",), read=True, output=READ_SCRIPTS_OUTPUT),
    tool("apply_script_changes", "Apply one context patch to live editor sources. Use *** Begin Patch, *** Add File: res://..., *** Update File: res://..., @@ context hunks and *** End Patch; hunk lines use space/-/+. Up to 100 sources; exact context, no whitespace fuzz. Independent concurrent edits merge against retained read bases; conflicts change nothing. One operation coordinates persistence, editor reload, source attachment and signals. Separate snapshot validation runs only when get_diagnostics is requested. By default wait up to 15 seconds for completion; pending work continues automatically and is queried by ID. Reload failures preserve applied and saved source. reload defaults to auto; defer pauses before explicit editor reload with RELOAD_DEFERRED; continue with resume_script_changes.", {"patch": {**TEXT, "minLength": 1}, "base_revisions": {**REVISIONS, "description": "Exactly the updated paths' revisions from read_scripts/find_assets; omit for an all-new patch."}, "save": {**B, "default": False, "description": "Persist this bundle's sources and binding owners; false leaves live changes. Saving does not imply valid source."}, "attachments": arr(SOURCE_ATTACHMENT, 100), "connections": SOURCE_CONNECTIONS, "reload": {**enum("auto", "defer"), "default": "auto", "description": "Editor reload policy; Godot may auto-reload independently."}, "preview": {**B, "description": "Return the same guarded text plan and save scope without applying or validating it."}, "wait_ms": {**integer(0, 15000), "default": 15000}}, ("patch",), output=PATCH_OUTPUT),
    tool("resume_script_changes", "Continue a blocked source bundle from its unfinished phase without replaying its patch, completed saves or successful bindings. Accepting changed source revisions repeats only the required source saves and reloads. After repairing source, provide every original source's current read revision. Target changes still cause conflicts. Continuations are bounded to 32 running/blocked bundles per editor session. reload defaults to auto; auto continues a previously deferred explicit reload.", {"operation_id": S, "revisions": REVISIONS, "reload": {**enum("auto", "defer"), "default": "auto", "description": "Editor reload policy; Godot may auto-reload independently."}, "wait_ms": {**integer(0, 15000), "default": 15000}}, ("operation_id",), output=DOCUMENT_OUTPUT),
    tool("update_signals", "Connect/disconnect persistent signal handlers with optional binds in one scene. Missing handler code is reported.", {"connect": arr(SIGNAL), "disconnect": arr(SIGNAL)}, idempotent=True),
    tool("get_animation", "Inspect animation tracks/keys or AnimationTree states, transitions, blend connections and parameter values.", {"node": REF, "animation": S}, ("node",), read=True),
    tool("edit_animation", "Create or edit an AnimationPlayer animation and typed tracks/keys. Local scope isolates a player's shared library; shared scope is explicit.", {"player": REF, "name": S, "create": B, "length": {"type": "number", "exclusiveMinimum": 0}, "loop": B, "tracks": arr(TRACK), "scope": enum("local", "shared")}, ("player", "name")),
    tool("edit_animation_graph", "Build state machines or blend trees/spaces with transitions, connections and parameters, as one undoable graph edit.", {"tree": REF, "root_type": enum("state_machine", "blend_tree"), "states": arr(obj({"name": S, "animation": S, "position": V2, "remove": B}, ("name",))), "transitions": arr(obj({"from": S, "to": S, "condition": S, "expression": TEXT, "advance": enum("auto", "enabled", "disabled"), "cross_fade": {"type": "number", "minimum": 0}, "remove": B}, ("from", "to")), 500), "nodes": arr(GRAPH_NODE), "remove_nodes": arr(S), "connections": arr(obj({"to": S, "input": integer(0, 32), "from": S}, ("to", "input", "from"))), "parameters": PROPS, "active": B}, ("tree",)),
    tool("preview_animation", "Interpolate a pose at a time, capture the real editor viewport, and restore values. Method/audio tracks are not executed.", {"player": REF, "name": S, "time": {"type": "number", "minimum": 0}, "capture": B, "viewport": enum("editor_2d", "editor_3d")}, ("player", "name", "time"), read=True),
    tool("get_tilemap", "Read TileMapLayer cells and reusable atlas/tile/terrain identifiers. Reads a bounded region or up to limit used cells.", {"layer": REF, "region": REGION, "limit": integer(1, 10000)}, ("layer",), read=True),
    tool("edit_tileset", "Batch atlas, collision and terrain edits on a staged TileSet with one undo. Choose a local node property or shared resource target explicitly.", {"target": SCOPED_TARGET, "changes": arr(TS_CHANGE, 500, 1)}, ("target", "changes")),
    tool("paint_tiles", "Paint cells, regions, patterns or terrain paths and report all actual changes including auto-connected neighbors. Undo restores prior cells.", {"layer": REF, "cells": arr(CELL, 10000), "region": obj({"origin": I2, "size": SIZE, "tile": TILE}, ("origin", "size", "tile")), "pattern": obj({"at": I2, "cells": arr(CELL, 10000, 1)}, ("at", "cells")), "terrain": obj({"set": integer(), "id": integer(-1), "cells": arr(I2, 10000, 1), "mode": enum("connect", "path"), "ignore_empty": B}, ("set", "id", "cells"))}, ("layer",)),
    tool("inspect_runtime", "Read the actual game's scene tree or node properties with run ID and observation time.", {"node": RUN_REF, "properties": arr(S), "depth": integer(0, 10)}, ("node",), read=True),
    tool("capture_viewport", "Return actual PNG pixels plus viewport/capture coordinates. viewport.kind may select game, editor_2d, editor_3d, or an editor_window; detached windows are selected with window_id from get_context.editor_windows. window_id and scene assert the selected window or active scene and do not open it. framing defaults to current; scene and selection frame editor content, while explicit bounds require non-current framing. rect is a pixel crop; max_width and max_height explicitly downscale, and omitted limits preserve original pixels. Window captures return client area. Headless rendering returns an explicit unsupported error.", {"viewport": obj({"kind": enum("game", "editor_2d", "editor_3d", "editor_window"), "run_id": S, "index": integer(0, 3), "window_id": integer(0), "scene": RES}, ("kind",)), "framing": {**enum("current", "scene", "selection"), "default": "current"}, "bounds_2d": obj({"origin": V2, "size": V2}, ("origin", "size")), "bounds_3d": obj({"position": V3, "size": V3}, ("position", "size")), "rect": {**obj({"origin": I2, "size": SIZE}, ("origin", "size")), "description": "Pixel crop applied after capture."}, "max_width": {**integer(1, 4096), "description": "Explicit output downscale width; omitted preserves original pixels."}, "max_height": {**integer(1, 4096), "description": "Explicit output downscale height; omitted preserves original pixels."}}, ("viewport",), read=True),
    tool("wait_for_condition", "Observe scene/node/property/signal conditions until satisfied or a bounded timeout; returns last observation.", {"run_id": S, "condition": CONDITION, "timeout_ms": integer(1, 60000), "poll_ms": integer(1, 1000)}, ("run_id", "condition"), read=True),
    tool("get_diagnostics", "Explicitly validate a captured snapshot of sources and unsaved dependencies; no historical logs or guarantee that the live project remains unchanged. Unrelated live edits do not discard captured results. Returns an operation_id immediately when validation exceeds wait_ms (default 15000); use get_operation_result to wait without repeating work. Omitted uris selects authored project sources, excluding this plugin. Counts describe only complete snapshot coverage; pending/unavailable is not error-free. Snapshots exclude dot caches/symlinks and are limited to 512 MiB/20,000 files.", {"uris": arr(RES, 200), "kinds": arr(enum("error", "warning"), 2), "wait_ms": {**integer(0, 15000), "default": 15000}}, read=True, output=DIAGNOSTICS_OUTPUT),
    tool("get_logs", "Read historical editor or selected-run log entries with cursor pagination. Log occurrence or silence does not establish whether current source is valid or a runtime problem is resolved.", {"run_id": S, "kinds": arr(enum("error", "warning", "log"), 3), "since": SAFE_COUNTER, "limit": integer(1, 1000)}, read=True, output=LOGS_OUTPUT),
    tool("sample_performance", "Measure supported Performance monitors over time; include units, sample count and conditions. Unknown metrics are rejected.", {"run_id": S, "duration_ms": integer(1, 60000), "metrics": arr(enum("process_ms", "physics_ms", "fps", "memory_bytes", "objects", "draw_calls", "primitives", "video_memory_bytes"), 8, 1)}, ("run_id", "duration_ms", "metrics"), read=True),
    tool("run_scene", "Start a game with a recorded startup source snapshot and runtime handshake. save_uris explicitly lists documents to persist first; other unsaved documents block startup. Optional revisions guard the expected sources. Startup file evidence does not prove changed behavior; use runtime observations.", {"scene": RES, "save_uris": arr(RES, 200), "revisions": REVISIONS, "restart": B}, output=RUN_OUTPUT),
    tool("stop_game", "Stop the specified run, release injected input, and confirm process termination.", {"run_id": S}, ("run_id",), idempotent=True),
    tool("send_input", "Send timestamped key/mouse/touch/action events through Godot input; each event selects exactly one named kind payload. Capture position and relative coordinates use capture pixels. Timeouts retain applied effects; retry failed observation or capture rather than repeating the mutation.", {"run_id": S, "events": arr(INPUT, 1000, 1), "capture_uri": S, "wait_for": CONDITION, "timeout_ms": integer(1, 60000), "capture_after": B, "release_after": B, "observe": arr(obj({"node": RUN_REF, "properties": arr(S, 32, 1)}, ("node", "properties")), 32, 1)}, ("run_id", "events"), output=SEND_INPUT_OUTPUT),
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
TOOL_HELP = {spec["name"]: spec["description"] for spec in TOOL_SPECS}
_SHORT_DESCRIPTIONS = {
    "get_guide": "Read the manual index, a section, or one tool's usage and schema (section=tools, tool=name).",
    "get_context": "Read connected projects and editor state. scope=progress reports active work; runtime_details opts into source provenance.",
    "get_operation_result": "Read retained operation results; wait_ms waits without repeating work. Snapshots and live recovery eligibility are separate.",
    "find_assets": "Search names, source text or symbols with query; mode=list lists files, folders and drafts without a query.",
    "delete_assets": "Preview then delete files/folders and companions. References block by default; allow_broken reports broken links. Permanent mode has no recovery.",
    "purge_deleted_assets": "Preview then permanently purge deletion backups. Purged backups cannot be restored or undone.",
    "restore_assets": "Restore a recoverable deletion or selected paths, including companions; returns actual restored files and synchronization state.",
    "save_documents": "Save listed authored documents; extra save scope must be explicit. Imports manage imported resources. Saving does not validate; Undo retains disk writes.",
    "read_scripts": "Read live sources/drafts and revisions for subsequent patches. Ranges use one-based Unicode columns and exclusive ends.",
    "apply_script_changes": "Apply a context patch with read revisions; optionally save and bind sources. Waits up to 15s; query pending work by ID. Diagnostics are explicit; reload=defer pauses reload.",
    "resume_script_changes": "Resume a blocked source bundle without replaying completed work. After repairs, provide every original source's current revision.",
    "capture_viewport": "Capture game/editor pixels with scene and coordinate metadata. framing fits editor content; rect crops; omitted size limits preserve original pixels.",
    "get_diagnostics": "Validate a source snapshot on request; waits up to 15s by default. Query pending operation_id without repeating. Pending/unavailable is not error-free; historical errors use get_logs.",
    "run_scene": "Start a game and confirm its handshake. Unsaved documents require explicit save_uris; startup evidence does not establish behavior.",
    "send_input": "Inject scheduled inputs; optionally observe properties before/after, wait for a condition and capture. Returns injection timing, not gameplay success. Do not replay after observation failure.",
}
for _spec in TOOL_SPECS:
    if _spec["name"] in _SHORT_DESCRIPTIONS:
        _spec["description"] = _SHORT_DESCRIPTIONS[_spec["name"]]
TOOL_HELP["send_input"] += " observe selects runtime nodes and properties for before/after reads. injection records contain event index, scheduled at_ms, injected_at_usec and frame. Equal-time events are injected together; condition, observation and capture timestamps identify their own moments. processed counts injected events, not game actions."

# Canonical input contracts and published tool schemas are the same definitions.
DOCUMENT_TOOLS = {"apply_script_changes", "resume_script_changes", "save_documents"}
SPECS = {spec["name"]: spec for spec in TOOL_SPECS}
assert len(SPECS) == len(TOOL_SPECS) == 50
