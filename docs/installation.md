# Installation

`godot-mcp` is started by the MCP client as a standard stdio server. The client launches one global `godot-mcp connect --home HOME` process; Godot does not launch a Python daemon. The global server discovers linked, currently open projects through the installation home and keeps project selection in the MCP connection.

## Global installation

Use the installer without `--project` to prepare the versioned executable and register the global client entry:

```bash
uv sync --frozen
uv run godot-mcp install --yes --home "$HOME/.local/share/godot-mcp" --client-config /path/to/client-mcp.json
```

The registered client command is equivalent to:

```text
/path/to/installed/godot-mcp connect --home /home/user/.local/share/godot-mcp
```

The exact home and executable paths are recorded by the installer. For Codex-compatible TOML registration, use `--client-format codex`; for VS Code JSON, use `--client-format vscode`.

Your AI app starts the stdio process. Open a linked Godot project and enable the installed Godot MCP plugin; the editor writes its authenticated endpoint and registration under the same installation home. Godot registers open projects, while the global server remains project-independent.

## Link a project

After a global environment exists, link or repair a project and refresh its plugin with:

```bash
uv run godot-mcp install --plugin-only --yes \
  --project /path/to/project \
  --home "$HOME/.local/share/godot-mcp"
```

Close all linked editors before updating their addon files. The installer records each linked project under `HOME/projects`, keeps the active executable in `HOME/active.json`, and stores client registrations in `HOME/clients.json`. Existing unrelated client settings and project settings are preserved.

## Connect and select

Start the registered client entry, or run the equivalent command manually:

```bash
/path/to/installed/godot-mcp connect --home "$HOME/.local/share/godot-mcp"
```

Every tool accepts an optional `project` selector when discovery is enabled. Call `get_context` first:

- with no open linked project, it reports a ready server and an empty project list (editor tools return `NO_OPEN_PROJECT`);
- with one open linked project, it selects that project automatically;
- with several open linked projects, it returns the project list and requires an absolute `project` path;
- after a successful selection, later calls in the same MCP connection reuse that project;
- if the selected project closes or becomes incompatible, calls fail with `PROJECT_CLOSED` or the corresponding connection error instead of silently switching projects.

A dedicated compatibility process remains available for scripts that already know the project:

```bash
uv run godot-mcp serve --project /path/to/project
```

## Verify

With the project open in Godot, verify the editor and catalog:

```bash
uv run godot-mcp check --project /path/to/project
```

The check reports the matching product, engine, protocol, and 42-tool catalog. A successful installation means files and registration were prepared; it does not by itself mean an editor is connected.

## Update and rollback

Run the global installer again with the same `HOME` to update the active executable and refresh all projects already recorded there. Close all linked editors first, then reopen them after the update. The installer validates the new environment before changing registrations.

Each global transaction records child project transactions plus snapshots of client configuration, `clients.json`, and `active.json`. Rolling back the global transaction restores all child project addon/project metadata and all global registrations/configuration from that transaction:

```bash
uv run godot-mcp install --rollback /path/to/home/transactions/TIMESTAMP-global
```

A project-only transaction can be rolled back independently when it was installed separately. Keep the transaction directory until the updated installation has passed connection and representative-tool checks.

## Troubleshooting

- `NO_OPEN_PROJECT`: open the project in Godot and enable the matching plugin.
- `PROJECT_REQUIRED`: call `get_context` with the absolute `project` path shown in the returned list.
- `PROJECT_CLOSED`: reopen the project or select another currently open project in a new call.
- `VERSION_MISMATCH`: update the project plugin and server from the same product release.
- `EDITOR_DISCONNECTED`: check that the plugin is enabled and that the endpoint belongs to the project being selected.

## Release bootstrap

Linux/macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.ps1 | iex
```

The bootstrap prepares uv and Python 3.13, selects the newest stable revision compatible with the detected Godot version, verifies the source archive's SHA-256 and size against the HTTPS release manifest, then installs using its `uv.lock`. No compatible release means no project changes. Godot and export templates are installed separately. Normal MCP startup reuses the installed environment without dependency downloads.

The installer detects Godot from PATH and common application locations and verifies its version. It asks for the executable path only if detection fails; `--godot PATH` always overrides discovery. With `--yes`, failed detection exits with guidance instead of prompting. Interactive defaults cover the install home, optional project, and detected client configuration. Unix piped installation uses `/dev/tty`. For unattended installation, download the wrapper and pass `--yes`, `--godot PATH`, `--home PATH`, and optional `--project PATH` / `--client-config PATH`. Omit the client config for copyable manual settings.

Re-running the bootstrap updates recorded projects and clients. `--version v4.7.2_1` pins an exact stable release; `--repair` prepares a fresh environment. Prior environments are retained. Close linked editors before updates or rollback. Rollback restores pre-install snapshots, including client/project settings; preserve later edits separately before explicitly rolling back.

Keep `.godot-mcp/` out of project version control; it contains machine-local linking data and an authentication token. The runtime autoload is inert when the engine debugger is unavailable. If you use a custom installation home, pass that same `--home` when linking additional projects.

Linux x86_64 is runtime-tested. macOS, Windows, and Linux ARM64 source packages are offered, with native validation still outstanding. DAP uses the editor's configured port or its `--dap-port` argument; `GODOT_MCP_DAP_PORT` can override it. Captures require a renderer; pausing outside GDScript may have no frame to step.

Installer subprocesses discard inherited virtual-environment targets and use `--link-mode copy`. This avoids mismatched-environment and cross-filesystem hardlink warnings without changing your shell or global uv settings. Dependency resolution still follows the release lock; installation may use slightly more disk space than hardlinks.
