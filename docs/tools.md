# Godot MCP tool reference

Generated from `godot_mcp.catalog.TOOL_SPECS`; schemas are JSON Schema Draft 2020-12.

| # | Tool | Description |
|---:|---|---|
| 1 | `install_plugin` | Install and enable the bundled plugin in an existing Godot project before connecting to the editor. Close the project in Godot first. Creates a rollback backup and registers project discovery. |
| 2 | `get_context` | Read project/engine/product/protocol versions, active scene, selection, unsaved documents and actual run state. |
| 3 | `find_assets` | Search filenames, source text or symbols. Returns reusable res:// URIs and one-based source locations. |
| 4 | `get_class_info` | Inspect actual engine or project script classes, properties, methods and signals; optionally filter a member. |
| 5 | `get_scene` | Inspect live scene nodes, unsaved values, connections, inheritance overrides and actual Control layout. |
| 6 | `open_scene` | Open and activate a saved scene in the editor. |
| 7 | `create_scene` | Create a scene with a typed root or inherited source. Saves the new file and returns its root reference. |
| 8 | `create_nodes` | Create a related subtree, scene instances or duplicates in one undoable edit. Returns actual names and references. |
| 9 | `update_nodes` | Batch node properties, names and reparenting in one scene. Use references in the source scene to edit the original. Container-controlled layout is reported. |
| 10 | `delete_nodes` | Delete related nodes with undo; report affected persistent connections and NodePath references. Reject inherited members and overlapping selections. |
| 11 | `save_documents` | Save only the specified scene, script or resource documents. Returns saved and failed entries separately. |
| 12 | `undo_edit` | Undo the latest MCP edit if its editor history has not changed since. Filesystem operations report their separate rollback scope. |
| 13 | `get_resource` | Read resource properties, nested references, known users and import provenance. Sharing scan covers open scenes and indexed project dependencies. |
| 14 | `create_resource` | Create an in-memory resource, optionally attach it or save it. Returns a reusable resource URI. |
| 15 | `update_resource` | Change a resource with explicit node-local or shared scope. Imported shared sources require detaching to an authored resource. |
| 16 | `read_script` | Read current unsaved GDScript or shader source, content revision and symbol positions. Ranges use one-based Unicode columns and exclusive ends. |
| 17 | `create_script` | Create GDScript or a shader and return compiler diagnostics. GDScript attaches to nodes; shaders attach to ShaderMaterial resources. |
| 18 | `edit_script` | Edit source using an exact revision and non-overlapping one-based ranges. Updates the live document; save explicitly to persist. |
| 19 | `update_signals` | Connect/disconnect persistent signal handlers with optional binds in one scene. Missing handler code is reported. |
| 20 | `get_animation` | Inspect animation tracks/keys or AnimationTree states, transitions, blend connections and parameter values. |
| 21 | `edit_animation` | Create or edit an AnimationPlayer animation and typed tracks/keys. Node scope isolates a player's shared library; shared scope is explicit. |
| 22 | `edit_animation_graph` | Build state machines or blend trees/spaces with transitions, connections and parameters, as one undoable graph edit. |
| 23 | `preview_animation` | Interpolate a pose at a time, capture the real editor viewport, and restore values. Method/audio tracks are not executed. |
| 24 | `get_tilemap` | Read TileMapLayer cells and reusable atlas/tile/terrain identifiers. Reads a bounded region or up to limit used cells. |
| 25 | `edit_tileset` | Author atlas tiles, collision polygons and terrain/peering rules on a staged TileSet, then commit with undo. |
| 26 | `paint_tiles` | Paint cells, regions, patterns or terrain paths and report all actual changes including auto-connected neighbors. Undo restores prior cells. |
| 27 | `inspect_runtime` | Read the actual game's scene tree or node properties with run ID and observation time. |
| 28 | `capture_viewport` | Return actual PNG pixels plus viewport/capture coordinates. Headless rendering returns an explicit unsupported error. |
| 29 | `wait_for_condition` | Observe scene/node/property/signal conditions until satisfied or a bounded timeout; returns last observation. |
| 30 | `get_diagnostics` | Read actual compiler/runtime/editor diagnostics with cursor, revision, repeat counts and source positions. |
| 31 | `sample_performance` | Measure supported Performance monitors over time; include units, sample count and conditions. Unknown metrics are rejected. |
| 32 | `run_scene` | Start an editor-launched game and wait for the actual runtime helper handshake. Save/restart are explicit (default false). |
| 33 | `stop_game` | Stop the specified run, release injected input, and confirm process termination. |
| 34 | `send_input` | Send timestamped key/mouse/touch/action events through Godot input. Optionally observe a condition and capture afterward. Capture URI enables conversion from image coordinates. |
| 35 | `inspect_debugger` | Read suspended DAP stack/scopes/variables; frame handles become stale on continue. GDScript is supported. |
| 36 | `set_breakpoints` | Add/remove MCP-owned breakpoints while preserving user breakpoints. replace=true replaces only MCP-owned entries. |
| 37 | `debug_control` | Pause, continue, step over or step into GDScript. step_out reports unsupported on Godot 4.7.2. |
| 38 | `get_settings` | Read project settings, input mappings and autoloads with property metadata. |
| 39 | `get_export_presets` | Read actual preset names/platforms and installed export-template readiness. |
| 40 | `import_assets` | Copy local assets or reimport project assets with options, wait for Godot import, and report resource references and persistence risks. |
| 41 | `move_assets` | Move project files with UID sidecars and reconcile serialized dependencies. Reject unsaved documents and report dynamic references needing review. |
| 42 | `update_settings` | Apply project settings/input actions/autoload changes with undo; save project.godot explicitly to persist. |
| 43 | `export_build` | Export with a real Godot preset via CLI and verify the output exists. Export success does not imply artifact execution. |

## Full input schemas

<details>
<summary>1. <code>install_plugin</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "project": {
      "description": "Required absolute path to the directory containing project.godot.",
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "project"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>2. <code>get_context</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "scope": {
      "enum": [
        "all",
        "project",
        "editor",
        "runtime"
      ],
      "type": "string"
    }
  },
  "required": [],
  "type": "object"
}
```

</details>

<details>
<summary>3. <code>find_assets</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "limit": {
      "maximum": 500,
      "minimum": 1,
      "type": "integer"
    },
    "mode": {
      "enum": [
        "name",
        "text",
        "symbol"
      ],
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "query": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "scope": {
      "pattern": "^res://",
      "type": "string"
    },
    "types": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "maxItems": 32,
      "minItems": 0,
      "type": "array"
    }
  },
  "required": [
    "query"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>4. <code>get_class_info</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "class": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "member": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "class"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>5. <code>get_scene</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "depth": {
      "maximum": 32,
      "minimum": 0,
      "type": "integer"
    },
    "path": {
      "maxLength": 2048,
      "minLength": 1,
      "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "properties": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "scene": {
      "maxLength": 4096,
      "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
      "type": "string"
    }
  },
  "required": [],
  "type": "object"
}
```

</details>

<details>
<summary>6. <code>open_scene</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "scene": {
      "maxLength": 4096,
      "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
      "type": "string"
    }
  },
  "required": [
    "scene"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>7. <code>create_scene</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "inherits": {
      "maxLength": 4096,
      "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "root_class": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "root_name": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "uri": {
      "maxLength": 4096,
      "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
      "type": "string"
    }
  },
  "required": [
    "uri",
    "root_name"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>8. <code>create_nodes</code></summary>

```json
{
  "$defs": {
    "node": {
      "additionalProperties": false,
      "oneOf": [
        {
          "required": [
            "class"
          ]
        },
        {
          "required": [
            "instance"
          ]
        },
        {
          "required": [
            "duplicate"
          ]
        }
      ],
      "properties": {
        "children": {
          "items": {
            "$ref": "#/$defs/node"
          },
          "maxItems": 100,
          "minItems": 0,
          "type": "array"
        },
        "class": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "duplicate": {
          "additionalProperties": false,
          "properties": {
            "path": {
              "maxLength": 2048,
              "minLength": 1,
              "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
              "type": "string"
            },
            "scene": {
              "maxLength": 4096,
              "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
              "type": "string"
            }
          },
          "required": [
            "scene",
            "path"
          ],
          "type": "object"
        },
        "instance": {
          "maxLength": 4096,
          "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
          "type": "string"
        },
        "key": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "name": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "properties": {
          "additionalProperties": {
            "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
          },
          "maxProperties": 200,
          "type": "object"
        }
      },
      "required": [
        "name"
      ],
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "nodes": {
      "items": {
        "$ref": "#/$defs/node"
      },
      "maxItems": 200,
      "minItems": 1,
      "type": "array"
    },
    "parent": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "maxLength": 2048,
          "minLength": 1,
          "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
          "type": "string"
        },
        "scene": {
          "maxLength": 4096,
          "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
          "type": "string"
        }
      },
      "required": [
        "scene",
        "path"
      ],
      "type": "object"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "parent",
    "nodes"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>9. <code>update_nodes</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "changes": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "index": {
            "maximum": 10000,
            "minimum": 0,
            "type": "integer"
          },
          "keep_global_transform": {
            "type": "boolean"
          },
          "name": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "node": {
            "additionalProperties": false,
            "properties": {
              "path": {
                "maxLength": 2048,
                "minLength": 1,
                "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
                "type": "string"
              },
              "scene": {
                "maxLength": 4096,
                "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
                "type": "string"
              }
            },
            "required": [
              "scene",
              "path"
            ],
            "type": "object"
          },
          "parent": {
            "additionalProperties": false,
            "properties": {
              "path": {
                "maxLength": 2048,
                "minLength": 1,
                "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
                "type": "string"
              },
              "scene": {
                "maxLength": 4096,
                "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
                "type": "string"
              }
            },
            "required": [
              "scene",
              "path"
            ],
            "type": "object"
          },
          "set": {
            "additionalProperties": {
              "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
            },
            "maxProperties": 200,
            "type": "object"
          }
        },
        "required": [
          "node"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 1,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "changes"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>10. <code>delete_nodes</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "nodes": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "path": {
            "maxLength": 2048,
            "minLength": 1,
            "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
            "type": "string"
          },
          "scene": {
            "maxLength": 4096,
            "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
            "type": "string"
          }
        },
        "required": [
          "scene",
          "path"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 1,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "nodes"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>11. <code>save_documents</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "save_as": {
      "additionalProperties": {
        "maxLength": 4096,
        "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
        "type": "string"
      },
      "type": "object"
    },
    "uris": {
      "items": {
        "pattern": "^(res://|godot://resources/).+",
        "type": "string"
      },
      "maxItems": 200,
      "minItems": 1,
      "type": "array"
    }
  },
  "required": [
    "uris"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>12. <code>undo_edit</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "edit_id": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "edit_id"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>13. <code>get_resource</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "depth": {
      "maximum": 5,
      "minimum": 0,
      "type": "integer"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "properties": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "target": {
      "additionalProperties": false,
      "oneOf": [
        {
          "required": [
            "uri"
          ]
        },
        {
          "required": [
            "node",
            "property"
          ]
        }
      ],
      "properties": {
        "node": {
          "additionalProperties": false,
          "properties": {
            "path": {
              "maxLength": 2048,
              "minLength": 1,
              "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
              "type": "string"
            },
            "scene": {
              "maxLength": 4096,
              "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
              "type": "string"
            }
          },
          "required": [
            "scene",
            "path"
          ],
          "type": "object"
        },
        "property": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "uri": {
          "pattern": "^(?:res://|godot://resources/).+",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "required": [
    "target"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>14. <code>create_resource</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "assign_to": {
      "additionalProperties": false,
      "properties": {
        "node": {
          "additionalProperties": false,
          "properties": {
            "path": {
              "maxLength": 2048,
              "minLength": 1,
              "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
              "type": "string"
            },
            "scene": {
              "maxLength": 4096,
              "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
              "type": "string"
            }
          },
          "required": [
            "scene",
            "path"
          ],
          "type": "object"
        },
        "property": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "node",
        "property"
      ],
      "type": "object"
    },
    "class": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "properties": {
      "additionalProperties": {
        "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
      },
      "maxProperties": 200,
      "type": "object"
    },
    "save_as": {
      "maxLength": 4096,
      "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
      "type": "string"
    }
  },
  "required": [
    "class"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>15. <code>update_resource</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "save_as": {
      "maxLength": 4096,
      "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
      "type": "string"
    },
    "scope": {
      "enum": [
        "node",
        "shared"
      ],
      "type": "string"
    },
    "set": {
      "additionalProperties": {
        "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
      },
      "maxProperties": 200,
      "type": "object"
    },
    "target": {
      "additionalProperties": false,
      "oneOf": [
        {
          "required": [
            "uri"
          ]
        },
        {
          "required": [
            "node",
            "property"
          ]
        }
      ],
      "properties": {
        "node": {
          "additionalProperties": false,
          "properties": {
            "path": {
              "maxLength": 2048,
              "minLength": 1,
              "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
              "type": "string"
            },
            "scene": {
              "maxLength": 4096,
              "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
              "type": "string"
            }
          },
          "required": [
            "scene",
            "path"
          ],
          "type": "object"
        },
        "property": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "uri": {
          "pattern": "^(?:res://|godot://resources/).+",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "required": [
    "target",
    "set",
    "scope"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>16. <code>read_script</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "range": {
      "additionalProperties": false,
      "properties": {
        "end": {
          "additionalProperties": false,
          "properties": {
            "column": {
              "maximum": 1000000,
              "minimum": 1,
              "type": "integer"
            },
            "line": {
              "maximum": 1000000,
              "minimum": 1,
              "type": "integer"
            }
          },
          "required": [
            "line",
            "column"
          ],
          "type": "object"
        },
        "start": {
          "additionalProperties": false,
          "properties": {
            "column": {
              "maximum": 1000000,
              "minimum": 1,
              "type": "integer"
            },
            "line": {
              "maximum": 1000000,
              "minimum": 1,
              "type": "integer"
            }
          },
          "required": [
            "line",
            "column"
          ],
          "type": "object"
        }
      },
      "required": [
        "start",
        "end"
      ],
      "type": "object"
    },
    "symbol": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "uri": {
      "maxLength": 4096,
      "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
      "type": "string"
    }
  },
  "required": [
    "uri"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>17. <code>create_script</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "attach_to": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "path": {
            "maxLength": 2048,
            "minLength": 1,
            "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
            "type": "string"
          },
          "scene": {
            "maxLength": 4096,
            "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
            "type": "string"
          }
        },
        "required": [
          "scene",
          "path"
        ],
        "type": "object"
      },
      "maxItems": 50,
      "minItems": 0,
      "type": "array"
    },
    "material": {
      "additionalProperties": false,
      "oneOf": [
        {
          "required": [
            "uri"
          ]
        },
        {
          "required": [
            "node",
            "property"
          ]
        }
      ],
      "properties": {
        "node": {
          "additionalProperties": false,
          "properties": {
            "path": {
              "maxLength": 2048,
              "minLength": 1,
              "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
              "type": "string"
            },
            "scene": {
              "maxLength": 4096,
              "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
              "type": "string"
            }
          },
          "required": [
            "scene",
            "path"
          ],
          "type": "object"
        },
        "property": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "uri": {
          "pattern": "^(?:res://|godot://resources/).+",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "source": {
      "maxLength": 1000000,
      "type": "string"
    },
    "uri": {
      "maxLength": 4096,
      "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
      "type": "string"
    }
  },
  "required": [
    "uri",
    "source"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>18. <code>edit_script</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "edits": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "range": {
            "additionalProperties": false,
            "properties": {
              "end": {
                "additionalProperties": false,
                "properties": {
                  "column": {
                    "maximum": 1000000,
                    "minimum": 1,
                    "type": "integer"
                  },
                  "line": {
                    "maximum": 1000000,
                    "minimum": 1,
                    "type": "integer"
                  }
                },
                "required": [
                  "line",
                  "column"
                ],
                "type": "object"
              },
              "start": {
                "additionalProperties": false,
                "properties": {
                  "column": {
                    "maximum": 1000000,
                    "minimum": 1,
                    "type": "integer"
                  },
                  "line": {
                    "maximum": 1000000,
                    "minimum": 1,
                    "type": "integer"
                  }
                },
                "required": [
                  "line",
                  "column"
                ],
                "type": "object"
              }
            },
            "required": [
              "start",
              "end"
            ],
            "type": "object"
          },
          "text": {
            "maxLength": 1000000,
            "type": "string"
          }
        },
        "required": [
          "range",
          "text"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 1,
      "type": "array"
    },
    "if_revision": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "uri": {
      "maxLength": 4096,
      "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
      "type": "string"
    }
  },
  "required": [
    "uri",
    "if_revision",
    "edits"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>19. <code>update_signals</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "connect": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "binds": {
            "items": {
              "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
            },
            "maxItems": 16,
            "minItems": 0,
            "type": "array"
          },
          "from": {
            "additionalProperties": false,
            "properties": {
              "path": {
                "maxLength": 2048,
                "minLength": 1,
                "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
                "type": "string"
              },
              "scene": {
                "maxLength": 4096,
                "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
                "type": "string"
              }
            },
            "required": [
              "scene",
              "path"
            ],
            "type": "object"
          },
          "method": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "signal": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "to": {
            "additionalProperties": false,
            "properties": {
              "path": {
                "maxLength": 2048,
                "minLength": 1,
                "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
                "type": "string"
              },
              "scene": {
                "maxLength": 4096,
                "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
                "type": "string"
              }
            },
            "required": [
              "scene",
              "path"
            ],
            "type": "object"
          }
        },
        "required": [
          "from",
          "signal",
          "to",
          "method"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "disconnect": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "binds": {
            "items": {
              "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
            },
            "maxItems": 16,
            "minItems": 0,
            "type": "array"
          },
          "from": {
            "additionalProperties": false,
            "properties": {
              "path": {
                "maxLength": 2048,
                "minLength": 1,
                "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
                "type": "string"
              },
              "scene": {
                "maxLength": 4096,
                "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
                "type": "string"
              }
            },
            "required": [
              "scene",
              "path"
            ],
            "type": "object"
          },
          "method": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "signal": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "to": {
            "additionalProperties": false,
            "properties": {
              "path": {
                "maxLength": 2048,
                "minLength": 1,
                "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
                "type": "string"
              },
              "scene": {
                "maxLength": 4096,
                "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
                "type": "string"
              }
            },
            "required": [
              "scene",
              "path"
            ],
            "type": "object"
          }
        },
        "required": [
          "from",
          "signal",
          "to",
          "method"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [],
  "type": "object"
}
```

</details>

<details>
<summary>20. <code>get_animation</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "animation": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "node": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "maxLength": 2048,
          "minLength": 1,
          "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
          "type": "string"
        },
        "scene": {
          "maxLength": 4096,
          "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
          "type": "string"
        }
      },
      "required": [
        "scene",
        "path"
      ],
      "type": "object"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "node"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>21. <code>edit_animation</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "create": {
      "type": "boolean"
    },
    "length": {
      "exclusiveMinimum": 0,
      "type": "number"
    },
    "loop": {
      "type": "boolean"
    },
    "name": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "player": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "maxLength": 2048,
          "minLength": 1,
          "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
          "type": "string"
        },
        "scene": {
          "maxLength": 4096,
          "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
          "type": "string"
        }
      },
      "required": [
        "scene",
        "path"
      ],
      "type": "object"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "scope": {
      "enum": [
        "node",
        "shared"
      ],
      "type": "string"
    },
    "tracks": {
      "items": {
        "additionalProperties": false,
        "anyOf": [
          {
            "required": [
              "index"
            ]
          },
          {
            "required": [
              "kind",
              "path"
            ]
          }
        ],
        "properties": {
          "enabled": {
            "type": "boolean"
          },
          "index": {
            "maximum": 2147483647,
            "minimum": 0,
            "type": "integer"
          },
          "interpolation": {
            "enum": [
              "nearest",
              "linear",
              "cubic"
            ],
            "type": "string"
          },
          "keys": {
            "items": {
              "additionalProperties": false,
              "properties": {
                "remove": {
                  "type": "boolean"
                },
                "time": {
                  "minimum": 0,
                  "type": "number"
                },
                "transition": {
                  "type": "number"
                },
                "value": {
                  "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
                }
              },
              "required": [
                "time"
              ],
              "type": "object"
            },
            "maxItems": 5000,
            "minItems": 0,
            "type": "array"
          },
          "kind": {
            "enum": [
              "value",
              "position_3d",
              "rotation_3d",
              "scale_3d",
              "method",
              "bezier"
            ],
            "type": "string"
          },
          "op": {
            "enum": [
              "add",
              "update",
              "remove"
            ],
            "type": "string"
          },
          "path": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "replace_keys": {
            "type": "boolean"
          }
        },
        "required": [],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    }
  },
  "required": [
    "player",
    "name"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>22. <code>edit_animation_graph</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "active": {
      "type": "boolean"
    },
    "connections": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "from": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "input": {
            "maximum": 32,
            "minimum": 0,
            "type": "integer"
          },
          "to": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          }
        },
        "required": [
          "to",
          "input",
          "from"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "nodes": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "animation": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "filter": {
            "items": {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            },
            "maxItems": 200,
            "minItems": 0,
            "type": "array"
          },
          "kind": {
            "enum": [
              "animation",
              "blend2",
              "add2",
              "blend3",
              "one_shot",
              "time_scale",
              "time_seek",
              "blend_space_1d",
              "blend_space_2d"
            ],
            "type": "string"
          },
          "max": {
            "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
          },
          "min": {
            "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
          },
          "name": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "points": {
            "items": {
              "additionalProperties": false,
              "properties": {
                "animation": {
                  "maxLength": 4096,
                  "minLength": 1,
                  "type": "string"
                },
                "position": {
                  "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
                }
              },
              "required": [
                "animation",
                "position"
              ],
              "type": "object"
            },
            "maxItems": 64,
            "minItems": 0,
            "type": "array"
          },
          "position": {
            "additionalProperties": false,
            "properties": {
              "x": {
                "type": "number"
              },
              "y": {
                "type": "number"
              }
            },
            "required": [
              "x",
              "y"
            ],
            "type": "object"
          }
        },
        "required": [
          "name",
          "kind"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "parameters": {
      "additionalProperties": {
        "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
      },
      "maxProperties": 200,
      "type": "object"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "remove_nodes": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "root_type": {
      "enum": [
        "state_machine",
        "blend_tree"
      ],
      "type": "string"
    },
    "states": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "animation": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "name": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "position": {
            "additionalProperties": false,
            "properties": {
              "x": {
                "type": "number"
              },
              "y": {
                "type": "number"
              }
            },
            "required": [
              "x",
              "y"
            ],
            "type": "object"
          },
          "remove": {
            "type": "boolean"
          }
        },
        "required": [
          "name"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "transitions": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "advance": {
            "enum": [
              "auto",
              "enabled",
              "disabled"
            ],
            "type": "string"
          },
          "condition": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "cross_fade": {
            "minimum": 0,
            "type": "number"
          },
          "expression": {
            "maxLength": 1000000,
            "type": "string"
          },
          "from": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "remove": {
            "type": "boolean"
          },
          "to": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          }
        },
        "required": [
          "from",
          "to"
        ],
        "type": "object"
      },
      "maxItems": 500,
      "minItems": 0,
      "type": "array"
    },
    "tree": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "maxLength": 2048,
          "minLength": 1,
          "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
          "type": "string"
        },
        "scene": {
          "maxLength": 4096,
          "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
          "type": "string"
        }
      },
      "required": [
        "scene",
        "path"
      ],
      "type": "object"
    }
  },
  "required": [
    "tree"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>23. <code>preview_animation</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "capture": {
      "type": "boolean"
    },
    "name": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "player": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "maxLength": 2048,
          "minLength": 1,
          "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
          "type": "string"
        },
        "scene": {
          "maxLength": 4096,
          "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
          "type": "string"
        }
      },
      "required": [
        "scene",
        "path"
      ],
      "type": "object"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "time": {
      "minimum": 0,
      "type": "number"
    },
    "viewport": {
      "enum": [
        "editor_2d",
        "editor_3d"
      ],
      "type": "string"
    }
  },
  "required": [
    "player",
    "name",
    "time"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>24. <code>get_tilemap</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "layer": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "maxLength": 2048,
          "minLength": 1,
          "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
          "type": "string"
        },
        "scene": {
          "maxLength": 4096,
          "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
          "type": "string"
        }
      },
      "required": [
        "scene",
        "path"
      ],
      "type": "object"
    },
    "limit": {
      "maximum": 10000,
      "minimum": 1,
      "type": "integer"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "region": {
      "additionalProperties": false,
      "properties": {
        "origin": {
          "additionalProperties": false,
          "properties": {
            "x": {
              "maximum": 1000000,
              "minimum": -1000000,
              "type": "integer"
            },
            "y": {
              "maximum": 1000000,
              "minimum": -1000000,
              "type": "integer"
            }
          },
          "required": [
            "x",
            "y"
          ],
          "type": "object"
        },
        "size": {
          "additionalProperties": false,
          "properties": {
            "x": {
              "maximum": 4096,
              "minimum": 1,
              "type": "integer"
            },
            "y": {
              "maximum": 4096,
              "minimum": 1,
              "type": "integer"
            }
          },
          "required": [
            "x",
            "y"
          ],
          "type": "object"
        }
      },
      "required": [
        "origin",
        "size"
      ],
      "type": "object"
    }
  },
  "required": [
    "layer"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>25. <code>edit_tileset</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "changes": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "alternative": {
            "maximum": 2147483647,
            "minimum": 0,
            "type": "integer"
          },
          "atlas": {
            "additionalProperties": false,
            "properties": {
              "x": {
                "maximum": 1000000,
                "minimum": -1000000,
                "type": "integer"
              },
              "y": {
                "maximum": 1000000,
                "minimum": -1000000,
                "type": "integer"
              }
            },
            "required": [
              "x",
              "y"
            ],
            "type": "object"
          },
          "collision_layer": {
            "maximum": 2147483647,
            "minimum": 0,
            "type": "integer"
          },
          "collision_mask": {
            "maximum": 2147483647,
            "minimum": 0,
            "type": "integer"
          },
          "key": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "mode": {
            "enum": [
              "corners_and_sides",
              "corners",
              "sides"
            ],
            "type": "string"
          },
          "one_way": {
            "type": "boolean"
          },
          "op": {
            "enum": [
              "add_atlas",
              "define_tile",
              "remove_tile",
              "add_physics_layer",
              "collision",
              "add_terrain_set",
              "terrain"
            ],
            "type": "string"
          },
          "peering_bits": {
            "additionalProperties": {
              "maximum": 255,
              "minimum": -1,
              "type": "integer"
            },
            "type": "object"
          },
          "physics_layer": {
            "maximum": 31,
            "minimum": 0,
            "type": "integer"
          },
          "polygons": {
            "items": {
              "items": {
                "additionalProperties": false,
                "properties": {
                  "x": {
                    "type": "number"
                  },
                  "y": {
                    "type": "number"
                  }
                },
                "required": [
                  "x",
                  "y"
                ],
                "type": "object"
              },
              "maxItems": 100,
              "minItems": 3,
              "type": "array"
            },
            "maxItems": 32,
            "minItems": 0,
            "type": "array"
          },
          "probability": {
            "minimum": 0,
            "type": "number"
          },
          "size": {
            "additionalProperties": false,
            "properties": {
              "x": {
                "maximum": 4096,
                "minimum": 1,
                "type": "integer"
              },
              "y": {
                "maximum": 4096,
                "minimum": 1,
                "type": "integer"
              }
            },
            "required": [
              "x",
              "y"
            ],
            "type": "object"
          },
          "source_id": {
            "maximum": 2147483647,
            "minimum": 0,
            "type": "integer"
          },
          "source_key": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "terrain": {
            "maximum": 2147483647,
            "minimum": -1,
            "type": "integer"
          },
          "terrain_set": {
            "maximum": 2147483647,
            "minimum": 0,
            "type": "integer"
          },
          "terrains": {
            "items": {
              "additionalProperties": false,
              "properties": {
                "color": {
                  "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
                },
                "name": {
                  "maxLength": 4096,
                  "minLength": 1,
                  "type": "string"
                }
              },
              "required": [
                "name"
              ],
              "type": "object"
            },
            "maxItems": 64,
            "minItems": 0,
            "type": "array"
          },
          "texture": {
            "maxLength": 4096,
            "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
            "type": "string"
          },
          "tile_size": {
            "additionalProperties": false,
            "properties": {
              "x": {
                "maximum": 4096,
                "minimum": 1,
                "type": "integer"
              },
              "y": {
                "maximum": 4096,
                "minimum": 1,
                "type": "integer"
              }
            },
            "required": [
              "x",
              "y"
            ],
            "type": "object"
          }
        },
        "required": [
          "op"
        ],
        "type": "object"
      },
      "maxItems": 500,
      "minItems": 1,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "scope": {
      "enum": [
        "node",
        "shared"
      ],
      "type": "string"
    },
    "target": {
      "additionalProperties": false,
      "oneOf": [
        {
          "required": [
            "uri"
          ]
        },
        {
          "required": [
            "node",
            "property"
          ]
        }
      ],
      "properties": {
        "node": {
          "additionalProperties": false,
          "properties": {
            "path": {
              "maxLength": 2048,
              "minLength": 1,
              "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
              "type": "string"
            },
            "scene": {
              "maxLength": 4096,
              "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
              "type": "string"
            }
          },
          "required": [
            "scene",
            "path"
          ],
          "type": "object"
        },
        "property": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "uri": {
          "pattern": "^(?:res://|godot://resources/).+",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "required": [
    "target",
    "changes"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>26. <code>paint_tiles</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "cells": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "cell": {
            "additionalProperties": false,
            "properties": {
              "x": {
                "maximum": 1000000,
                "minimum": -1000000,
                "type": "integer"
              },
              "y": {
                "maximum": 1000000,
                "minimum": -1000000,
                "type": "integer"
              }
            },
            "required": [
              "x",
              "y"
            ],
            "type": "object"
          },
          "tile": {
            "additionalProperties": false,
            "properties": {
              "alternative": {
                "maximum": 2147483647,
                "minimum": 0,
                "type": "integer"
              },
              "atlas": {
                "additionalProperties": false,
                "properties": {
                  "x": {
                    "maximum": 1000000,
                    "minimum": -1000000,
                    "type": "integer"
                  },
                  "y": {
                    "maximum": 1000000,
                    "minimum": -1000000,
                    "type": "integer"
                  }
                },
                "required": [
                  "x",
                  "y"
                ],
                "type": "object"
              },
              "source_id": {
                "maximum": 2147483647,
                "minimum": -1,
                "type": "integer"
              }
            },
            "required": [
              "source_id"
            ],
            "type": "object"
          }
        },
        "required": [
          "cell",
          "tile"
        ],
        "type": "object"
      },
      "maxItems": 10000,
      "minItems": 0,
      "type": "array"
    },
    "layer": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "maxLength": 2048,
          "minLength": 1,
          "pattern": "^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*:).+",
          "type": "string"
        },
        "scene": {
          "maxLength": 4096,
          "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
          "type": "string"
        }
      },
      "required": [
        "scene",
        "path"
      ],
      "type": "object"
    },
    "pattern": {
      "additionalProperties": false,
      "properties": {
        "at": {
          "additionalProperties": false,
          "properties": {
            "x": {
              "maximum": 1000000,
              "minimum": -1000000,
              "type": "integer"
            },
            "y": {
              "maximum": 1000000,
              "minimum": -1000000,
              "type": "integer"
            }
          },
          "required": [
            "x",
            "y"
          ],
          "type": "object"
        },
        "cells": {
          "items": {
            "additionalProperties": false,
            "properties": {
              "cell": {
                "additionalProperties": false,
                "properties": {
                  "x": {
                    "maximum": 1000000,
                    "minimum": -1000000,
                    "type": "integer"
                  },
                  "y": {
                    "maximum": 1000000,
                    "minimum": -1000000,
                    "type": "integer"
                  }
                },
                "required": [
                  "x",
                  "y"
                ],
                "type": "object"
              },
              "tile": {
                "additionalProperties": false,
                "properties": {
                  "alternative": {
                    "maximum": 2147483647,
                    "minimum": 0,
                    "type": "integer"
                  },
                  "atlas": {
                    "additionalProperties": false,
                    "properties": {
                      "x": {
                        "maximum": 1000000,
                        "minimum": -1000000,
                        "type": "integer"
                      },
                      "y": {
                        "maximum": 1000000,
                        "minimum": -1000000,
                        "type": "integer"
                      }
                    },
                    "required": [
                      "x",
                      "y"
                    ],
                    "type": "object"
                  },
                  "source_id": {
                    "maximum": 2147483647,
                    "minimum": -1,
                    "type": "integer"
                  }
                },
                "required": [
                  "source_id"
                ],
                "type": "object"
              }
            },
            "required": [
              "cell",
              "tile"
            ],
            "type": "object"
          },
          "maxItems": 10000,
          "minItems": 1,
          "type": "array"
        }
      },
      "required": [
        "at",
        "cells"
      ],
      "type": "object"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "region": {
      "additionalProperties": false,
      "properties": {
        "origin": {
          "additionalProperties": false,
          "properties": {
            "x": {
              "maximum": 1000000,
              "minimum": -1000000,
              "type": "integer"
            },
            "y": {
              "maximum": 1000000,
              "minimum": -1000000,
              "type": "integer"
            }
          },
          "required": [
            "x",
            "y"
          ],
          "type": "object"
        },
        "size": {
          "additionalProperties": false,
          "properties": {
            "x": {
              "maximum": 4096,
              "minimum": 1,
              "type": "integer"
            },
            "y": {
              "maximum": 4096,
              "minimum": 1,
              "type": "integer"
            }
          },
          "required": [
            "x",
            "y"
          ],
          "type": "object"
        },
        "tile": {
          "additionalProperties": false,
          "properties": {
            "alternative": {
              "maximum": 2147483647,
              "minimum": 0,
              "type": "integer"
            },
            "atlas": {
              "additionalProperties": false,
              "properties": {
                "x": {
                  "maximum": 1000000,
                  "minimum": -1000000,
                  "type": "integer"
                },
                "y": {
                  "maximum": 1000000,
                  "minimum": -1000000,
                  "type": "integer"
                }
              },
              "required": [
                "x",
                "y"
              ],
              "type": "object"
            },
            "source_id": {
              "maximum": 2147483647,
              "minimum": -1,
              "type": "integer"
            }
          },
          "required": [
            "source_id"
          ],
          "type": "object"
        }
      },
      "required": [
        "origin",
        "size",
        "tile"
      ],
      "type": "object"
    },
    "terrain": {
      "additionalProperties": false,
      "properties": {
        "cells": {
          "items": {
            "additionalProperties": false,
            "properties": {
              "x": {
                "maximum": 1000000,
                "minimum": -1000000,
                "type": "integer"
              },
              "y": {
                "maximum": 1000000,
                "minimum": -1000000,
                "type": "integer"
              }
            },
            "required": [
              "x",
              "y"
            ],
            "type": "object"
          },
          "maxItems": 10000,
          "minItems": 1,
          "type": "array"
        },
        "id": {
          "maximum": 2147483647,
          "minimum": -1,
          "type": "integer"
        },
        "ignore_empty": {
          "type": "boolean"
        },
        "mode": {
          "enum": [
            "connect",
            "path"
          ],
          "type": "string"
        },
        "set": {
          "maximum": 2147483647,
          "minimum": 0,
          "type": "integer"
        }
      },
      "required": [
        "set",
        "id",
        "cells"
      ],
      "type": "object"
    }
  },
  "required": [
    "layer"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>27. <code>inspect_runtime</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "depth": {
      "maximum": 10,
      "minimum": 0,
      "type": "integer"
    },
    "node": {
      "additionalProperties": false,
      "properties": {
        "path": {
          "maxLength": 2048,
          "pattern": "^/root(?:/|$)",
          "type": "string"
        },
        "run_id": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "run_id",
        "path"
      ],
      "type": "object"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "properties": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    }
  },
  "required": [
    "node"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>28. <code>capture_viewport</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "max_height": {
      "maximum": 4096,
      "minimum": 1,
      "type": "integer"
    },
    "max_width": {
      "maximum": 4096,
      "minimum": 1,
      "type": "integer"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "rect": {
      "additionalProperties": false,
      "properties": {
        "origin": {
          "additionalProperties": false,
          "properties": {
            "x": {
              "maximum": 1000000,
              "minimum": -1000000,
              "type": "integer"
            },
            "y": {
              "maximum": 1000000,
              "minimum": -1000000,
              "type": "integer"
            }
          },
          "required": [
            "x",
            "y"
          ],
          "type": "object"
        },
        "size": {
          "additionalProperties": false,
          "properties": {
            "x": {
              "maximum": 4096,
              "minimum": 1,
              "type": "integer"
            },
            "y": {
              "maximum": 4096,
              "minimum": 1,
              "type": "integer"
            }
          },
          "required": [
            "x",
            "y"
          ],
          "type": "object"
        }
      },
      "required": [
        "origin",
        "size"
      ],
      "type": "object"
    },
    "viewport": {
      "additionalProperties": false,
      "properties": {
        "index": {
          "maximum": 3,
          "minimum": 0,
          "type": "integer"
        },
        "kind": {
          "enum": [
            "game",
            "editor_2d",
            "editor_3d"
          ],
          "type": "string"
        },
        "run_id": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        }
      },
      "required": [
        "kind"
      ],
      "type": "object"
    }
  },
  "required": [
    "viewport"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>29. <code>wait_for_condition</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "condition": {
      "additionalProperties": false,
      "allOf": [
        {
          "if": {
            "properties": {
              "type": {
                "const": "scene"
              }
            }
          },
          "then": {
            "required": [
              "uri"
            ]
          }
        },
        {
          "if": {
            "properties": {
              "type": {
                "const": "node"
              }
            }
          },
          "then": {
            "required": [
              "node"
            ]
          }
        },
        {
          "if": {
            "properties": {
              "type": {
                "const": "property"
              }
            }
          },
          "then": {
            "required": [
              "node",
              "property",
              "value"
            ]
          }
        },
        {
          "if": {
            "properties": {
              "type": {
                "const": "signal"
              }
            }
          },
          "then": {
            "required": [
              "node",
              "signal"
            ]
          }
        }
      ],
      "properties": {
        "exists": {
          "type": "boolean"
        },
        "node": {
          "additionalProperties": false,
          "properties": {
            "path": {
              "maxLength": 2048,
              "pattern": "^/root(?:/|$)",
              "type": "string"
            },
            "run_id": {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            }
          },
          "required": [
            "run_id",
            "path"
          ],
          "type": "object"
        },
        "operator": {
          "enum": [
            "eq",
            "ne",
            "gt",
            "gte",
            "lt",
            "lte"
          ],
          "type": "string"
        },
        "property": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "signal": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "type": {
          "enum": [
            "scene",
            "node",
            "property",
            "signal"
          ],
          "type": "string"
        },
        "uri": {
          "maxLength": 4096,
          "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
          "type": "string"
        },
        "value": {
          "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
        }
      },
      "required": [
        "type"
      ],
      "type": "object"
    },
    "poll_ms": {
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "run_id": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "timeout_ms": {
      "maximum": 60000,
      "minimum": 1,
      "type": "integer"
    }
  },
  "required": [
    "run_id",
    "condition"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>30. <code>get_diagnostics</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "kinds": {
      "items": {
        "enum": [
          "error",
          "warning",
          "log"
        ],
        "type": "string"
      },
      "maxItems": 3,
      "minItems": 0,
      "type": "array"
    },
    "limit": {
      "maximum": 1000,
      "minimum": 1,
      "type": "integer"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "revision": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "run_id": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "since": {
      "maximum": 2147483647,
      "minimum": 0,
      "type": "integer"
    },
    "uris": {
      "items": {
        "maxLength": 4096,
        "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
        "type": "string"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    }
  },
  "required": [],
  "type": "object"
}
```

</details>

<details>
<summary>31. <code>sample_performance</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "duration_ms": {
      "maximum": 60000,
      "minimum": 1,
      "type": "integer"
    },
    "metrics": {
      "items": {
        "enum": [
          "process_ms",
          "physics_ms",
          "fps",
          "memory_bytes",
          "objects",
          "draw_calls",
          "primitives",
          "video_memory_bytes"
        ],
        "type": "string"
      },
      "maxItems": 8,
      "minItems": 1,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "run_id": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "run_id",
    "duration_ms",
    "metrics"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>32. <code>run_scene</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "restart": {
      "type": "boolean"
    },
    "save": {
      "type": "boolean"
    },
    "scene": {
      "maxLength": 4096,
      "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
      "type": "string"
    }
  },
  "required": [],
  "type": "object"
}
```

</details>

<details>
<summary>33. <code>stop_game</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "run_id": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "run_id"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>34. <code>send_input</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "capture_after": {
      "type": "boolean"
    },
    "capture_uri": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "events": {
      "items": {
        "additionalProperties": false,
        "allOf": [
          {
            "if": {
              "properties": {
                "type": {
                  "const": "key"
                }
              }
            },
            "then": {
              "required": [
                "key",
                "pressed"
              ]
            }
          },
          {
            "if": {
              "properties": {
                "type": {
                  "const": "mouse_button"
                }
              }
            },
            "then": {
              "required": [
                "button",
                "position",
                "pressed"
              ]
            }
          },
          {
            "if": {
              "properties": {
                "type": {
                  "const": "mouse_motion"
                }
              }
            },
            "then": {
              "required": [
                "position"
              ]
            }
          },
          {
            "if": {
              "properties": {
                "type": {
                  "const": "touch"
                }
              }
            },
            "then": {
              "required": [
                "position",
                "pressed"
              ]
            }
          },
          {
            "if": {
              "properties": {
                "type": {
                  "const": "drag"
                }
              }
            },
            "then": {
              "required": [
                "position",
                "relative"
              ]
            }
          },
          {
            "if": {
              "properties": {
                "type": {
                  "const": "action"
                }
              }
            },
            "then": {
              "required": [
                "action",
                "pressed"
              ]
            }
          }
        ],
        "properties": {
          "action": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "alt": {
            "type": "boolean"
          },
          "at_ms": {
            "maximum": 60000,
            "minimum": 0,
            "type": "integer"
          },
          "button": {
            "enum": [
              "left",
              "right",
              "middle",
              "wheel_up",
              "wheel_down"
            ],
            "type": "string"
          },
          "ctrl": {
            "type": "boolean"
          },
          "index": {
            "maximum": 15,
            "minimum": 0,
            "type": "integer"
          },
          "key": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "meta": {
            "type": "boolean"
          },
          "physical": {
            "type": "boolean"
          },
          "position": {
            "additionalProperties": false,
            "properties": {
              "x": {
                "type": "number"
              },
              "y": {
                "type": "number"
              }
            },
            "required": [
              "x",
              "y"
            ],
            "type": "object"
          },
          "pressed": {
            "type": "boolean"
          },
          "relative": {
            "additionalProperties": false,
            "properties": {
              "x": {
                "type": "number"
              },
              "y": {
                "type": "number"
              }
            },
            "required": [
              "x",
              "y"
            ],
            "type": "object"
          },
          "shift": {
            "type": "boolean"
          },
          "strength": {
            "maximum": 1,
            "minimum": 0,
            "type": "number"
          },
          "type": {
            "enum": [
              "key",
              "mouse_button",
              "mouse_motion",
              "touch",
              "drag",
              "action"
            ],
            "type": "string"
          }
        },
        "required": [
          "type"
        ],
        "type": "object"
      },
      "maxItems": 1000,
      "minItems": 1,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "release_after": {
      "type": "boolean"
    },
    "run_id": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "timeout_ms": {
      "maximum": 60000,
      "minimum": 1,
      "type": "integer"
    },
    "wait_for": {
      "additionalProperties": false,
      "allOf": [
        {
          "if": {
            "properties": {
              "type": {
                "const": "scene"
              }
            }
          },
          "then": {
            "required": [
              "uri"
            ]
          }
        },
        {
          "if": {
            "properties": {
              "type": {
                "const": "node"
              }
            }
          },
          "then": {
            "required": [
              "node"
            ]
          }
        },
        {
          "if": {
            "properties": {
              "type": {
                "const": "property"
              }
            }
          },
          "then": {
            "required": [
              "node",
              "property",
              "value"
            ]
          }
        },
        {
          "if": {
            "properties": {
              "type": {
                "const": "signal"
              }
            }
          },
          "then": {
            "required": [
              "node",
              "signal"
            ]
          }
        }
      ],
      "properties": {
        "exists": {
          "type": "boolean"
        },
        "node": {
          "additionalProperties": false,
          "properties": {
            "path": {
              "maxLength": 2048,
              "pattern": "^/root(?:/|$)",
              "type": "string"
            },
            "run_id": {
              "maxLength": 4096,
              "minLength": 1,
              "type": "string"
            }
          },
          "required": [
            "run_id",
            "path"
          ],
          "type": "object"
        },
        "operator": {
          "enum": [
            "eq",
            "ne",
            "gt",
            "gte",
            "lt",
            "lte"
          ],
          "type": "string"
        },
        "property": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "signal": {
          "maxLength": 4096,
          "minLength": 1,
          "type": "string"
        },
        "type": {
          "enum": [
            "scene",
            "node",
            "property",
            "signal"
          ],
          "type": "string"
        },
        "uri": {
          "maxLength": 4096,
          "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
          "type": "string"
        },
        "value": {
          "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
        }
      },
      "required": [
        "type"
      ],
      "type": "object"
    }
  },
  "required": [
    "run_id",
    "events"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>35. <code>inspect_debugger</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "frame_id": {
      "maximum": 2147483647,
      "minimum": 0,
      "type": "integer"
    },
    "pause_id": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "run_id": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "variables_reference": {
      "maximum": 2147483647,
      "minimum": 0,
      "type": "integer"
    }
  },
  "required": [
    "run_id"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>36. <code>set_breakpoints</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "breakpoints": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "enabled": {
            "type": "boolean"
          },
          "line": {
            "maximum": 1000000,
            "minimum": 1,
            "type": "integer"
          },
          "uri": {
            "maxLength": 4096,
            "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
            "type": "string"
          }
        },
        "required": [
          "uri",
          "line"
        ],
        "type": "object"
      },
      "maxItems": 500,
      "minItems": 0,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "replace": {
      "type": "boolean"
    }
  },
  "required": [
    "breakpoints"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>37. <code>debug_control</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "action": {
      "enum": [
        "pause",
        "continue",
        "step_over",
        "step_into",
        "step_out"
      ],
      "type": "string"
    },
    "pause_id": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "run_id": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "run_id",
    "action"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>38. <code>get_settings</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "include": {
      "items": {
        "enum": [
          "project",
          "input_actions",
          "autoload"
        ],
        "type": "string"
      },
      "maxItems": 3,
      "minItems": 0,
      "type": "array"
    },
    "keys": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "maxItems": 500,
      "minItems": 0,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [],
  "type": "object"
}
```

</details>

<details>
<summary>39. <code>get_export_presets</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "platform": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "preset": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [],
  "type": "object"
}
```

</details>

<details>
<summary>40. <code>import_assets</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "files": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "destination": {
            "maxLength": 4096,
            "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
            "type": "string"
          },
          "options": {
            "additionalProperties": {
              "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
            },
            "maxProperties": 200,
            "type": "object"
          },
          "overwrite": {
            "type": "boolean"
          },
          "source": {
            "maxLength": 4096,
            "pattern": "^file:///",
            "type": "string"
          }
        },
        "required": [
          "destination"
        ],
        "type": "object"
      },
      "maxItems": 500,
      "minItems": 1,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "files"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>41. <code>move_assets</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "moves": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "from": {
            "maxLength": 4096,
            "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
            "type": "string"
          },
          "to": {
            "maxLength": 4096,
            "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
            "type": "string"
          }
        },
        "required": [
          "from",
          "to"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 1,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    }
  },
  "required": [
    "moves"
  ],
  "type": "object"
}
```

</details>

<details>
<summary>42. <code>update_settings</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "autoloads": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "enabled": {
            "type": "boolean"
          },
          "name": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "path": {
            "maxLength": 4096,
            "pattern": "^res://(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\).+",
            "type": "string"
          },
          "remove": {
            "type": "boolean"
          }
        },
        "required": [
          "name"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "input_actions": {
      "items": {
        "additionalProperties": false,
        "properties": {
          "deadzone": {
            "maximum": 1,
            "minimum": 0,
            "type": "number"
          },
          "events": {
            "items": {
              "additionalProperties": false,
              "properties": {
                "alt": {
                  "type": "boolean"
                },
                "axis": {
                  "maximum": 15,
                  "minimum": 0,
                  "type": "integer"
                },
                "axis_value": {
                  "type": "number"
                },
                "button": {
                  "maximum": 32,
                  "minimum": 0,
                  "type": "integer"
                },
                "ctrl": {
                  "type": "boolean"
                },
                "key": {
                  "maxLength": 4096,
                  "minLength": 1,
                  "type": "string"
                },
                "meta": {
                  "type": "boolean"
                },
                "physical": {
                  "type": "boolean"
                },
                "shift": {
                  "type": "boolean"
                },
                "type": {
                  "enum": [
                    "key",
                    "mouse_button",
                    "joypad_button",
                    "joypad_motion"
                  ],
                  "type": "string"
                }
              },
              "required": [
                "type"
              ],
              "type": "object"
            },
            "maxItems": 64,
            "minItems": 0,
            "type": "array"
          },
          "name": {
            "maxLength": 4096,
            "minLength": 1,
            "type": "string"
          },
          "remove": {
            "type": "boolean"
          }
        },
        "required": [
          "name"
        ],
        "type": "object"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "remove": {
      "items": {
        "maxLength": 4096,
        "minLength": 1,
        "type": "string"
      },
      "maxItems": 200,
      "minItems": 0,
      "type": "array"
    },
    "settings": {
      "additionalProperties": {
        "description": "JSON or tagged Godot value: $type=Vector2/Vector2i/Vector3/Vector3i/Vector4/Quaternion/Color/Rect2/Rect2i/Transform2D/Transform3D/Basis/NodePath/StringName/Resource or a Packed*Array. Resource uses uri returned by get_resource/create_resource. Color space is linear (default) or srgb."
      },
      "maxProperties": 200,
      "type": "object"
    }
  },
  "required": [],
  "type": "object"
}
```

</details>

<details>
<summary>43. <code>export_build</code></summary>

```json
{
  "additionalProperties": false,
  "properties": {
    "debug": {
      "type": "boolean"
    },
    "output": {
      "maxLength": 4096,
      "pattern": "^file:///",
      "type": "string"
    },
    "preset": {
      "maxLength": 4096,
      "minLength": 1,
      "type": "string"
    },
    "project": {
      "description": "Optional absolute project path. Select explicitly when several editors are open.",
      "minLength": 1,
      "type": "string"
    },
    "timeout_ms": {
      "maximum": 180000,
      "minimum": 1000,
      "type": "integer"
    }
  },
  "required": [
    "preset",
    "output"
  ],
  "type": "object"
}
```

</details>
