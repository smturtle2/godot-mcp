# godot-mcp

<p align="center">
  <img src="docs/assets/hero-blueprint.png" alt="Godot MCP scene blueprint" width="900">
</p>

<p align="center"><strong>Inspect, edit, run, and debug Godot projects through MCP.</strong><br>Work with scenes, scripts, and a running game from your AI assistant.</p>

<p align="center"><a href="README.ko.md">한국어</a> · <a href="README.md">English</a></p>

<p align="center">
<a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/Godot-4.7.2-478cbf?logo=godotengine&logoColor=white" alt="Godot 4.7.2"></a>
<a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/MCP-2026--07--28-5b5bd6" alt="MCP 2026-07-28"></a>
<a href="https://www.python.org/downloads/release/python-3130/"><img src="https://img.shields.io/badge/Python-3.13-3776ab?logo=python&logoColor=white" alt="Python 3.13"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-EUPL--1.2-green" alt="EUPL-1.2 license"></a>
</p>

## Get started

Requires **Godot 4.7.2** and a local stdio MCP client. Tested on Linux x86_64; other native platforms are not yet verified.

### 1. Install

Linux/macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.sh | sh
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/smturtle2/godot-mcp/main/install.ps1 | iex
```

Installs the latest release without prompts. Open a new terminal to use `godot-mcp`.

### 2. Connect your AI assistant

Send this prompt to your agent:

```text
Set up Godot MCP using this guide: https://github.com/smturtle2/godot-mcp/blob/main/docs/installation.md#agent-setup
```

### 3. Set up a project

Close the project in Godot and ask your AI to install the plugin in its absolute project directory. Then open the project in Godot and start working. Your MCP client runs the server automatically.

You can also run `godot-mcp init` from the project folder. For updates, close linked Godot projects, rerun the installer, and reconnect MCP.

Source editing follows the current Godot editor buffers: read related files with `read_scripts`, then submit one context patch with `apply_script_changes`. Changes stay unsaved by default and use editor Undo. Current diagnostics and resumable source operations support repairing failures without repeating completed work. Explicit reloads can be deferred and continued with `resume_script_changes`. Capture game or editor viewports, including whole editor windows, with pixel crop and scale metadata. See the [source workflow](docs/workflows.md#source-workflow).

Preview and delete files or folders through MCP, recover them with Undo or `restore_assets`, or explicitly choose permanent deletion.

## Reference

[49 tools](docs/tools.md) · [State and recovery](docs/workflows.md) · [Setup and troubleshooting](docs/installation.md) · [Development](docs/development.md) · [EUPL-1.2](LICENSE)
