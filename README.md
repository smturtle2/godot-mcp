# godot-mcp

<p align="center">
  <img src="docs/assets/hero-blueprint.png" alt="Godot MCP scene blueprint" width="900">
</p>

<p align="center"><strong>Inspect, edit, run, and debug Godot projects through MCP.</strong><br>Work with scenes, scripts, and a running game from your AI assistant.</p>

<p align="center"><a href="README.ko.md">한국어</a> · <a href="README.md">English</a></p>

<p align="center">
<a href="https://github.com/smturtle2/godot-mcp/releases/latest"><img src="https://img.shields.io/github/v/release/smturtle2/godot-mcp" alt="Latest release"></a>
<a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/Godot-4.7.2-478cbf?logo=godotengine&logoColor=white" alt="Godot 4.7.2"></a>
<a href="https://github.com/smturtle2/godot-mcp/releases"><img src="https://img.shields.io/badge/MCP-2026--07--28-5b5bd6" alt="MCP 2026-07-28"></a>
<a href="https://www.python.org/downloads/release/python-3130/"><img src="https://img.shields.io/badge/Python-3.13-3776ab?logo=python&logoColor=white" alt="Python 3.13"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-EUPL--1.2-green" alt="EUPL-1.2 license"></a>
</p>

## What you can do

- Edit live scenes, nodes, scripts, resources, and signals, including unsaved editor content.
- Author animations, animation graphs, TileSets, and tile maps; configure project settings and input actions.
- Run games, send input, capture game views or editor windows, inspect GDScript debugging state, and sample performance.
- Import, move, and delete assets with reference handling and recoverable deletion; export builds using project presets.

The server includes an English manual through `get_guide`: capabilities, Godot development choices, editor concepts, task examples, recovery, and tool selection. Your agent can read it through MCP, even before an editor is connected.

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

Installs the latest release without prompts and manages the required Python runtime. Open a new terminal to use `godot-mcp`.

### 2. Connect your AI assistant

Send this prompt to your agent:

```text
Set up Godot MCP using this guide: https://github.com/smturtle2/godot-mcp/blob/main/src/godot_mcp/guide_content/start.md#connect-the-mcp-client
```

The client starts the server with the stable launcher's absolute path and the `connect` argument. See the [connection guide](src/godot_mcp/guide_content/start.md#connect-the-mcp-client) for platform paths.

### 3. Set up a project

For a new project, ask your agent to use `create_project` with an absolute directory. It creates the project, installs the plugin, launches Godot, and connects.

Close an existing project in Godot and ask your agent to install its plugin with `install_plugin`, providing the project's absolute directory. Then open the project in Godot. The agent can use `get_context` to inspect it or select among several open projects.

You can also run `godot-mcp init` from the project folder. For updates, close linked Godot projects, rerun the installer, and reconnect MCP.

## Working with the agent

Describe the change or problem in ordinary language. The server instructions direct the agent to `get_guide` for relevant usage and development guidance. The development section explains Godot's technical options without imposing a game style or project architecture.

Edits use the current editor state. Source changes remain unsaved by default; saving and source diagnostics are separate operations. Pending operations can be followed without repeating the mutation. Editor Undo and recoverable asset deletion have different persistence rules, explained in the [usage examples](src/godot_mcp/guide_content/work.md) and [recovery guide](src/godot_mcp/guide_content/recovery.md).

## Reference

[Setup](src/godot_mcp/guide_content/start.md) · [Godot development](src/godot_mcp/guide_content/development.md) · [Editor concepts](src/godot_mcp/guide_content/model.md) · [Usage](src/godot_mcp/guide_content/work.md) · [Recovery](src/godot_mcp/guide_content/recovery.md) · [50 tools](docs/tools.md)

[Contributing and server development](docs/development.md) · [Changelog](CHANGELOG.md) · [EUPL-1.2](LICENSE)
