# Tool choices

The index below lists each tool's role. Read one tool's full usage, argument schema, and example when needed:

```json
{"section":"tools","tool":"create_nodes"}
```

Use `work` for task workflows and `model` for editor, resource, and runtime concepts. `create_project` prepares an empty directory through editor connection; its optional environment passes only the supported display/session variables. `install_plugin` links an existing closed project.

For unfinished work, query its `operation_id` with `get_operation_result`; use `resume_script_changes` only for a blocked source bundle. `get_logs` reads historical editor or selected-run history, including retained runtime entries while paused or stopped; `get_diagnostics` explicitly validates a source snapshot. Saving, validation, and runtime behavior are separate facts, summarized in mutation receipts whose state summary includes only evidenced stages.
