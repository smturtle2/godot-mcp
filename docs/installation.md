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
- Read a source revision before editing. Use `edit_script` for a whole-source replacement or ranges, and `apply_script_changes` for related files. A batch checks every revision before applying and validates all final sources together, including unsaved dependencies. `save` defaults to `false`; new batch sources can remain drafts, with live compilation deferred until they are saved.
- Source operations report `status`, document/validation state, pending saves, and undo scope. `partial`/`failed` results set MCP `isError`; successful steps remain applied. `create_script` saves before validating/attaching, so fix a failed creation with `edit_script`. Reading diagnostics successfully can report invalid source without being a tool failure.
- Save explicitly. Godot scene saves may also persist linked external resources; `also_saved` reports extra saves observed in source buffers. Undo changes live editor state; it does not roll back saved disk files. Unsaved batch drafts are removed on undo. Running game hot reload is not verified.
- Diagnostics use a fresh project copy plus live source overlays, bounded to 20,000 files, 512 MiB, and a compilation time budget. Editor log entries are history; use each source's `state` for current validity. Concurrent changes, unsupported symlinks, timeouts, or unresolved autoload singletons produce `pending`/`unavailable`, never a success claim. Scenes, plugins, and autoloads are not started in the compiler copy; Godot may still execute static initializers while compiling preloads. Native extensions/custom imports need editor verification.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Command not found | Open a new terminal or use the installer's absolute command. |
| MCP client cannot start the server | Check the stable executable path and the separate `connect` argument. |
| No open project / editor disconnected | Open a linked project in Godot with its plugin enabled. |
| Project selection required | Choose an absolute project path from `get_context`. |
| Version mismatch | Use the supported Godot version and matching server/plugin release. |

Keep the project's `.godot-mcp/` directory out of version control; it contains local linking data and an authentication token.
