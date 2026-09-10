# godot-mcp

<p align="center">
  <img src="docs/assets/hero-blueprint.png" alt="Godot MCP scene blueprint" width="900">
</p>

<p align="center"><strong>Inspect, edit, run, and debug Godot projects through MCP.</strong><br>
Work with scenes, scripts, and a running game from your AI assistant.</p>

<p align="center">
  <a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/Godot-4.7.2-478cbf?logo=godotengine&logoColor=white" alt="Godot 4.7.2"></a>
  <a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/MCP-2026--07--28-5b5bd6" alt="MCP 2026-07-28"></a>
  <a href="https://www.python.org/downloads/release/python-3130/"><img src="https://img.shields.io/badge/Python-3.13-3776ab?logo=python&logoColor=white" alt="Python 3.13"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-EUPL--1.2-green" alt="EUPL-1.2 license"></a>
</p>

## Get started

Requires a supported Godot runtime (current release: **4.7.2**) and an MCP client that supports local stdio servers. Linux x86_64 is tested; native testing on macOS, Windows, and Linux ARM64 is pending.

### 1. Install the latest release

Linux/macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.ps1 | iex
```

The public bootstrap fetches the latest stable release from GitHub Releases. It does not detect or ask for a Godot executable. The installer prepares the server environment and prints a generic stdio command; client registration and launch remain your MCP client’s responsibility.

### 2. Ask your AI to install the project plugin

Open your AI app with the registered stdio server and ask it to install the Godot plugin for an absolute project directory. The `install_plugin` setup tool uses the server’s configured `--home` and the same transactional installer used by the CLI. It can run before any Godot editor connection exists.

Close the project in Godot before installation. The tool installs and enables the plugin; then open the project in Godot. Ask your AI:

> Check the connected Godot project and describe the current scene.

The server discovers open linked projects. If several are open, tell the assistant which absolute project path to use; the selection is remembered for that MCP connection.

### CLI alternative

Use `init` when you want to link the current folder (or the project path you provide) from a terminal:

```bash
/path/to/installed/godot-mcp init /path/to/project --home /path/to/godot-mcp-home
```

With no project argument, `init` uses the current folder. Use the executable and installation home printed by the installer. A source checkout can use the explicit developer workflow:

```bash
uv sync --frozen
uv run godot-mcp install --source "$PWD" --home /path/to/godot-mcp-home
```

After updates, the installed executable path may change. Update the MCP client’s stdio command to the newly printed path; there is no stable launcher in this release.

See [setup and troubleshooting](docs/installation.md) for connection checks, updates, and rollback.

## Tools

There are **43 tools**: 42 editor/runtime tools plus the `install_plugin` setup tool. They cover scenes, scripts, resources, animation, TileMaps, game input, debugging, and exports. Changes can be inspected before saving; runtime tools report observations from the running game.

Browse the [tool reference](docs/tools.md) for all tool descriptions and input schemas.

## Development

See [development](docs/development.md) for setup, tests, and releases, or [architecture](docs/architecture.md) for the server and Godot plugin design.

## License

[EUPL-1.2](LICENSE).
