# Start here

Godot MCP connects an agent to a Godot editor. It can inspect and edit scenes, nodes, scripts, resources, signals, animations, TileSets, project settings, and assets. It can launch games, send input, capture editor or game pixels, read logs, inspect a paused GDScript run, sample performance, and export with an existing preset. The guide header identifies the installed server and supported engine version.

The manual has six sections: `start`, `development`, `model`, `work`, `recovery`, and `tools`. Omit `section` in `get_guide` to read the index. Select one of those exact names to read its full body. Subheadings such as UI are part of a section, not additional selector values. The guide itself works without a selected project or running Godot editor.

## Connect the MCP client

Configure the client's MCP entry with transport `stdio`, the stable launcher's absolute path as the command, and `["connect"]` as the arguments. Keep command and arguments separate. Use the client's supported setup interface or configuration format and preserve unrelated settings.

| Platform | Default stable launcher |
|---|---|
| Linux / macOS | `~/.local/share/godot-mcp/bin/godot-mcp` |
| Windows | `%LOCALAPPDATA%\godot-mcp\bin\godot-mcp.exe` |

Expand these paths to absolute paths in client configuration. On Linux/macOS, use `$XDG_DATA_HOME` in place of `~/.local/share` when configured. A custom installation home takes precedence. If no launcher is installed, use the installer from the [Godot MCP repository](https://github.com/smturtle2/godot-mcp). Reconnect the MCP client after changing its configuration; some clients require a restart.

## Link and select a project

To start a new project, or prepare an empty directory, call `create_project` with its required absolute path. The optional `name` defaults to the directory name; `editor` defaults to `GODOT`, then `godot` or `godot4` on `PATH`:

```json
{"project":"/absolute/path/to/new-game","name":"New Game"}
```

This creates `project.godot`, reuses the bundled plugin installer, launches the editor, and waits up to 15 seconds for the MCP handshake. The result reports `project_created`, `plugin_installed`, `editor_started`, and `connected`; a partial result includes failures and can be retried. Retries resume the recorded setup, preserve existing project settings, and do not launch another editor while the recorded process is alive. Use `install_plugin` for an unrelated existing project.

The server and the project's editor plugin are separate parts. With the project closed in Godot, install its plugin through `install_plugin`:

```json
{"project":"/absolute/path/to/project"}
```

The directory must already contain `project.godot`. CLI `godot-mcp init` performs the same project linking. Then open the project in Godot with the plugin enabled. `get_context` reports available projects or the selected editor state. When several projects are available, select one by passing its absolute `project` path to `get_context`; subsequent editor calls can omit it for that MCP connection. A server started for a dedicated project stays bound to that project.

`get_context` exposes the active scene, selection, unsaved state, and runtime information. Use the `work` section for task examples, `model` for references and state, and `recovery` if a connection or operation fails. An optional terminal connection check is `godot-mcp check --project /absolute/path/to/project` while Godot is open.

Keep `.godot-mcp/` out of version control: it contains local linking data and an authentication token, as well as operation recovery data. To update the installation, close linked projects, rerun the installer for the same home, and reconnect MCP. The stable launcher path remains unchanged. Installer options include `--home`, `--project`, `--repair`, `--rollback TRANSACTION`, and `--no-modify-path`; `godot-mcp install --help` describes them. Installer transaction backups live under `<install-home>/transactions/`.

## Scope and support

Editor tools operate on live state, including unsaved changes. They are useful when editing a project already open in Godot. Direct file editing remains an option when a feature is unsupported or the editor is offline; account for unsaved buffers and the reload/import needed to bring disk changes into the editor. The guide does not describe the current project's state: live inspection tools do.

- `get_class_info` inspects actual engine or project script members. It supplies metadata, not the full Godot API manual.
- `create_resource` directly instantiates engine Resource classes available through `ClassDB`; a custom script class name is not supported by that creation path. Reading and editing existing resources is a separate operation.
- Viewport capture needs a supported renderer and display. Headless captures are unsupported. Editor window capture covers the client area; game input does not control editor panels.
- Debugging tools support GDScript. DAP `step_out` is unsupported in the supported Godot version.
- Asset reference discovery covers known dependencies and authored references; dynamically assembled paths and external references can remain outside its coverage.
- Export uses real presets and installed templates. It reports artifact creation, not whether the resulting application runs correctly.

Use `tools` to choose among current capabilities. Engine design choices are covered in `development`; API support limits do not dictate a game's genre, style, or architecture.
