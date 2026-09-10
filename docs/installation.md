# Setup and troubleshooting

`godot-mcp` is a client-started MCP server over local stdio. The MCP client launches the registered command when needed; you do not run a separate server terminal. Open Godot separately. The public bootstrap installs the latest stable release and does not detect, prompt for, or pin a Godot executable or engine version.

## Install the server

Linux/macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.ps1 | iex
```

The installer owns the versioned server environment, project plugin/linking records, active executable, and project index. It prints a generic command such as:

```text
/path/to/godot-mcp-home/bin/godot-mcp connect
```

Register that fixed command with your MCP client using its own setup flow. The launcher selects the active server version on every start, so updates keep the same registered path. Reconnect MCP after an update.

The installer creates a user command inside its installation home and adds its `bin` directory to the user PATH. Open a new terminal to run `godot-mcp`. For managed installations, pass `--no-modify-path`; the printed absolute command works immediately without PATH changes.

## Install the project plugin with your AI

With the stdio server registered, ask your AI assistant to install the plugin for an absolute project directory. The `install_plugin` setup tool uses the server’s configured `--home` and the existing transactional installer. It works before any Godot connection exists.

Close the project in Godot before installing its plugin. The installer enables the plugin automatically; open the project after installation. The editor then publishes its authenticated endpoint for discovery.

## CLI alternative

`init` performs the same project linking flow from a terminal. Its default project is the current folder:

```bash
godot-mcp init /path/to/project --home /path/to/godot-mcp-home
godot-mcp init --home /path/to/godot-mcp-home
```

The stable command remembers its installation home; `--home` is normally unnecessary. An explicit source checkout remains available for developers:

```bash
uv sync --frozen
uv run godot-mcp install --source /path/to/godot-mcp --home /path/to/godot-mcp-home
```

The older project-bound form remains useful when a client already supplies the project:

```bash
godot-mcp serve --project /path/to/project
```

## Connect and select

Every editor/runtime tool accepts an optional absolute `project` selector when discovery is enabled. Call `get_context` first:

- one open linked project is selected automatically;
- several open projects are listed and require an explicit project path;
- a successful selection is remembered for the MCP connection;
- a closed or incompatible selected project returns an error instead of silently switching.

The setup tool is the exception: `install_plugin` takes an absolute project directory and can prepare the plugin without an active editor connection.

## Verify and update

Ask the AI to call `get_context`, or use the compatibility check while Godot is open:

```bash
godot-mcp check --project /path/to/project
```

A successful installation means the server environment and project plugin were prepared. Connection compatibility is checked against the supported Godot runtime when the editor connects; the current release targets Godot 4.7.2.

Close linked Godot projects before updating. Re-run the installer with the same home, or use `init`/`install_plugin` to refresh a project. Global transactions retain child project transactions and restore installer-owned server/project state on rollback. MCP client registration is outside that transaction.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| The client cannot start the server | Check the printed executable path and `connect --home` arguments; use the fixed absolute command for GUI clients. |
| `NO_OPEN_PROJECT` | Open a linked project in Godot and enable the plugin. |
| `PROJECT_REQUIRED` | Ask the AI to select an absolute project path from `get_context`. |
| `PROJECT_CLOSED` | Reopen the project or select another open project. |
| `EDITOR_DISCONNECTED` | Check that the project is open and the plugin is enabled. |
| `VERSION_MISMATCH` | Use the supported Godot runtime and matching server/plugin release. |

Keep the project’s `.godot-mcp/` directory out of version control; it contains machine-local linking data and an authentication token.
