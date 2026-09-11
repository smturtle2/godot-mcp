# Setup

For installation and first use, see the [README](../README.md).

## Agent setup

Follow these steps when asked to connect the installed Godot MCP server. Project plugin installation is a separate step.

1. Identify the user's MCP client from the current context. Use its supported setup interface or documented configuration format; ask which client only if the target is unclear.
2. Locate the stable `godot-mcp` launcher from PATH or the command printed by the installer. Use the launcher inside the installation home's `bin` directory. For a default installation, check the paths below; honor a custom installation home when provided.
3. Add or update the matching Godot MCP entry, preserving unrelated settings. Set transport to `stdio`, command to the launcher's absolute path, and arguments to `["connect"]`. Keep the executable path and argument separate.
4. Reload the client's MCP connection if supported. Verify that `tools/list` exposes `get_context` and `install_plugin`. Godot does not need to be open for this check. If a restart is required, explain the next step and leave verification pending until it can be performed.
5. Report the configured command, verification result, and any required user action.

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

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Command not found | Open a new terminal or use the installer's absolute command. |
| MCP client cannot start the server | Check the stable executable path and the separate `connect` argument. |
| No open project / editor disconnected | Open a linked project in Godot with its plugin enabled. |
| Project selection required | Choose an absolute project path from `get_context`. |
| Version mismatch | Use the supported Godot version and matching server/plugin release. |

Keep the project's `.godot-mcp/` directory out of version control; it contains local linking data and an authentication token.
