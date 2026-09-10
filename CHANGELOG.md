# v4.7.2_7

- Make installation unattended by default: use the standard user directory without project, path, or confirmation prompts. Keep `--home` and `--project` as explicit options and accept legacy `--yes` for compatibility.
- Present a compact three-step terminal status and ready-to-use commands. Color is limited to interactive terminals, with plain output for logs and `NO_COLOR`.
- Keep routine dependency output quiet while preserving subprocess error details on failure.

# v4.7.2_6

- Install a stable user command and register its directory on the user's shell PATH. The command follows the active installation, so server updates keep the same CLI and MCP executable path.
- Keep MCP client configuration and process ownership with the client. Print the stable absolute stdio command for GUI clients.
- Add `--no-modify-path` for isolated or managed installations; command creation and rollback remain inside the installation home.
- Rewrite the getting-started instructions around `godot-mcp init` and include the Korean `README.ko.md` in the repository and release archive.

# v4.7.2_4

- Add `godot-mcp init [PROJECT]` and the `install_plugin` MCP tool to install and enable a project plugin before an editor connection exists. The catalog now contains 43 tools.
- Simplify the README and user/developer references; remove obsolete planning, research, and validation documents.
- Public bootstrap installs the latest stable release from GitHub Releases.
- Installer ownership is limited to the server environment, project plugin/linking, active executable, and project index; MCP client registration and launch remain client responsibilities.
- Installer does not detect, prompt for, or pin a Godot executable or installed engine version; compatibility is checked when connecting to a supported editor.

# v4.7.2_3

- Remove all MCP-client discovery, configuration-file editing, and automatic registration from the installer. Connection registration and process launch are entirely the client's responsibility.
- Remove `--client-config`, `--client-format`, and `--name` installer options and the configuration-writing module/dependency. The installer prints only a generic stdio command.
- Ignore legacy client-registration records during updates. Rollback restores only server/project state and never external app settings, including old transaction snapshots.

# v4.7.2_2

- Allow updates when a stopped editor leaves a previous-version endpoint behind. The installer verifies the recorded process is gone before disregarding that stale endpoint; running editors still block plugin updates.
- Includes the automatic Godot discovery and warning-free uv installation improvements from v4.7.2_1.

# v4.7.2_1

- Automatically locate and validate Godot; prompt for its executable only when discovery fails. `--godot` remains an override; `--yes` never waits for input.
- Share standalone bootstrap detection with the installer to keep release/source installs consistent.
- Isolate installer subprocess environments and explicitly copy dependencies, preventing inherited-environment and cross-filesystem hardlink warnings without suppressing diagnostics.
- Keep the existing HTTPS bootstrap path compatible. No tool schema changes.

# v4.7.2_0

Initial Godot 4.7.2 integration with 42 MCP tools.

- Live editor scenes, inherited/instanced nodes, resources, scripts and signals with explicit save and guarded undo.
- Animation tracks/graphs and pose preview; TileSet/TileMapLayer authoring, collision and terrain operations.
- Editor-launched game observation, input, condition waits, viewport capture and performance samples.
- GDScript source breakpoints, stack/scopes/variables and debugger stepping through Godot's DAP adapter.
- Asset import/move, settings and real export execution.
- Official MCP Python SDK 2.2.0, protocol 2026-07-28, Python 3.13 and uv.lock-based versioned installation.
- User-wide installation and MCP registration, automatic open-project discovery, and per-session project selection.
- SHA-256 release manifest, configuration preservation, repair and transaction rollback.
- EUPL-1.2 licensing.

Linux x86_64 editor/game workflows are tested. macOS/Windows source installation wrappers are provided; native runtime validation on those platforms remains outstanding. The integration requires Godot 4.7.2. `step_out` is unsupported by this engine's DAP adapter. A pause outside GDScript has no inspectable frame; use a source breakpoint. Rendered captures require a renderer. Export success is reported separately from artifact execution.
