# Setup

For installation and first use, see the [README](../README.md).

## Agent setup

Follow these steps when asked to connect the installed Godot MCP server. Project plugin installation is a separate step.

1. Identify the user's MCP client from the current context. Use its supported setup interface or documented configuration format; ask which client only if the target is unclear.
2. Locate the stable `godot-mcp` launcher from PATH or the command printed by the installer. Use the launcher inside the installation home's `bin` directory. For a default installation, check the paths below; honor a custom installation home when provided.
3. Add or update the matching Godot MCP entry, preserving unrelated settings. Set transport to `stdio`, command to the launcher's absolute path, and arguments to `["connect"]`. Keep the executable path and argument separate.
4. Reload the client's MCP connection if supported. Verify that `tools/list` exposes `get_context` and `install_plugin`. Godot does not need to be open for this check. If a restart is required, explain the next step and leave verification pending until it can be performed.
5. Report the configured command, verification result, and any required user action.

While the editor is open, prefer Godot MCP for scene, script, resource, and project-setting changes. Direct edits can miss unsaved changes, bypass editor undo, and leave loaded resources stale until reimport/reload; MCP handles live state and reports revision, diagnostics, save, and undo details where supported. Direct editing remains appropriate when MCP is unsupported or offline: check unsaved state first, then verify reimport/reload and editor diagnostics.

Share these editing considerations with delegated agents working on the project.

| Platform | Default launcher |
| --- | --- |
| Linux / macOS | `~/.local/share/godot-mcp/bin/godot-mcp` |
| Windows | `%LOCALAPPDATA%\godot-mcp\bin\godot-mcp.exe` |

On Linux/macOS, use `$XDG_DATA_HOME` in place of `~/.local/share` when set. If the launcher is missing, follow the README's installation step before configuring the client.

## Projects and updates

- Install a project plugin with `install_plugin` or `godot-mcp init` while that project is closed in Godot. Then open it and call `get_context`.
- With several open projects, provide an absolute `project` path. Selection is remembered for the MCP connection.
- To update, close linked Godot projects, rerun the installer with the same installation home, and reconnect MCP. The launcher path stays the same.
- For a terminal connection check, run `godot-mcp check --project /path/to/project` while Godot is open.

Advanced installer options: `--home PATH`, `--project PATH`, `--repair`, `--rollback TRANSACTION`, and `--no-modify-path`. See `godot-mcp install --help` for details. Transaction backups are stored in `<install-home>/transactions/`.

## Editing and results

- `get_scene` returns structure by default. Request named `properties` or optional `include` sections for details; `properties: []` returns none. `create_nodes` uses flat records with `key`/`parent_key` links for hierarchy.
- Read current sources and revisions with `read_scripts`, then use one `apply_script_changes` context patch for Add/Update changes. Supply `base_revisions` for updated paths. Retained read bases allow independent concurrent edits to merge; overlapping or ambiguous edits conflict before application. `save` defaults to `false`, including new drafts; `preview` shows the plan without applying it.
- Source operations coordinate persistence, validation, reload and bindings. A `pending` receipt identifies ongoing work; query `get_operation_result` instead of repeating the patch. `partial`/`failed` results set MCP `isError` while successful steps remain applied. Repair source with a new patch, then use `resume_script_changes` with current revisions for every original source to continue unfinished phases. Reading diagnostics successfully can report invalid source without being a tool failure.
- Save explicitly. `save: true` persists sources before validation, so a later failure leaves those files saved. Scene saves require explicit scope for linked edited sources; `SAVE_SCOPE_REQUIRED` identifies additional URIs to include. Undo changes live editor state and preserves saved disk files. Unsaved new drafts are removed on undo. `run_scene.save_uris` lists documents to save before launch; other unsaved state blocks startup. Runtime `source_provenance` identifies changed sources and restart needs; verify behavior with runtime observations.
- `get_diagnostics` checks current sources using a project snapshot with live source and settings overlays, bounded to 20,000 files, 512 MiB, and a compilation time budget. An unchanged full fingerprint permits bounded cache reuse. Pending diagnostics have an operation ID. Use `get_logs` for historical editor/runtime entries and each diagnostic source's `state` for current validity. Concurrent changes, excluded dependencies, timeouts, or unresolved autoload singletons produce `pending`/`unavailable`, never an error-free claim. Scenes, plugins, and autoloads are not started in the compiler copy; Godot may still execute static initializers while compiling preloads. Native extensions/custom imports need editor verification.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Command not found | Open a new terminal or use the installer's absolute command. |
| MCP client cannot start the server | Check the stable executable path and the separate `connect` argument. |
| No open project / editor disconnected | Open a linked project in Godot with its plugin enabled. |
| Project selection required | Choose an absolute project path from `get_context`. |
| Version mismatch | Use the supported Godot version and matching server/plugin release. |

Keep the project's `.godot-mcp/` directory out of version control; it contains local linking data and an authentication token.
