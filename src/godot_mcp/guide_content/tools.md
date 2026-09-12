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
