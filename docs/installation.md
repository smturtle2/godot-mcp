# Installation

`godot-mcp` is started by the MCP client as a standard stdio server. The client launches one global `godot-mcp connect --home HOME` process; Godot does not launch a Python daemon. Client registration and process launch are entirely client responsibilities.

## Install the server environment

The installer owns the user-level server environment and project integration records. It does not detect, edit, or register any particular MCP client.

```bash
uv sync --frozen
uv run godot-mcp install --yes --home /path/to/godot-mcp-home
```

The installer prepares a versioned executable and prints a generic command equivalent to:

```text
/path/to/installed/godot-mcp connect --home /path/to/godot-mcp-home
```

Register that command using your MCP client’s own setup flow. No named client product or client-specific configuration path is required by this project.

## Link a project

With the server environment prepared, close the project in Godot and link or repair it with:

```bash
/path/to/installed/godot-mcp install --plugin-only --yes \
  --project /path/to/project \
  --home /path/to/godot-mcp-home
```

The installer copies the matching Godot plugin and records the project link under `HOME/projects`. It also maintains `HOME/active.json`. Open the project again and enable the installed plugin. Godot then publishes its authenticated endpoint for discovery.

## Connect and select

Start the generic stdio command through your MCP client, or run it manually:

```bash
/path/to/installed/godot-mcp connect --home /path/to/godot-mcp-home
```

Every tool accepts an optional `project` selector when discovery is enabled. Call `get_context` first:

- with no open linked project, it reports a ready server and an empty project list;
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

The check reports the matching product, engine, protocol, and 42-tool catalog. A successful installation means the environment and project plugin were prepared; it does not by itself mean an editor is connected.

## Update and rollback

Run the installer again with the same `HOME` to update the active executable and refresh projects already recorded there. Close all linked editors first, then reopen them after the update. The installer validates the new environment before changing project files.

Each global transaction records child project transactions plus snapshots of the active executable and project index. Rolling back the global transaction restores all child project addon/project metadata and the global active/index state:

```bash
/path/to/installed/godot-mcp install --rollback /path/to/home/transactions/TIMESTAMP-global
```

A project-only transaction can be rolled back independently when it was installed separately. Client registration changes, if any, are outside the installer transaction and must be managed by the client.

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

The bootstrap prepares uv and Python, verifies the release manifest, and invokes the same environment/project installer. It prints the generic `connect --home` command; configure that command in the MCP client yourself. Godot and export templates are installed separately.

The installer detects Godot from PATH and common application locations and verifies its version. It asks for the executable path only if detection fails; `--godot PATH` always overrides discovery. With `--yes`, failed detection exits with guidance instead of prompting. Pass `--home PATH` and, when linking, `--project PATH`. No stable launcher is provided by this repository.

Keep `.godot-mcp/` out of project version control; it contains machine-local linking data and an authentication token. Linux x86_64 is runtime-tested; native validation on other supported platforms remains outstanding.
