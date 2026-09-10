# Godot MCP requirements traceability inventory

Source: `godot-mcp-plan-v4.7.2_0.html` (the Korean development request). Each tool below is implemented and exercised by the real Godot acceptance suite. “Verified workflow” refers to representative paths, not every possible argument combination. See [validation evidence](validation.md). JSON snippets in the source are illustrative call shapes; exact schemas and tool inputs may be refined during implementation while preserving the intent and acceptance criteria.

## Tool catalog (42 tools)

| # | Tool | Intent | Key acceptance criteria | Status |
|---:|---|---|---|---|
| 1 | `get_context` | Read current project/editor context. | Returns project, engine and MCP versions, active scene, selection, unsaved documents and run state; distinguishes current editor state. | Verified workflow |
| 2 | `find_assets` | Find files, resources and code by name or context. | Returns matching paths, locations and surrounding context usable by follow-up read/edit calls. | Verified workflow |
| 3 | `get_class_info` | Inspect Godot class members and types. | Reports properties, methods and signals valid for the actual Godot version. | Verified workflow |
| 4 | `get_scene` | Read scene tree, nodes, properties, scripts and connections. | Includes unsaved edits and distinguishes inherited/instanced/original values; returns node references and layout relationships. | Verified workflow |
| 5 | `open_scene` | Open and activate a scene in the editor. | Returns the opened scene and activation state. | Verified workflow |
| 6 | `create_scene` | Create a new scene. | Accepts root type/name/path and optional inheritance; returns the scene and root reference ready for child creation. | Verified workflow |
| 7 | `create_nodes` | Create a node group or subtree. | Applies types, names, properties and hierarchy; returns actual created paths and results, including instance/duplicate flows where applicable. | Verified workflow |
| 8 | `update_nodes` | Change node properties, placement, names or parents. | Returns changed values, paths, affected connections and actual UI placement; explains inheritance/layout changes that cannot apply. | Verified workflow |
| 9 | `delete_nodes` | Delete nodes and subtrees. | Reports deleted targets, affected references and failures; explains protected/inherited items and broken connections. | Verified workflow |
| 10 | `save_documents` | Save selected scene, script or resource changes. | Clearly distinguishes editor-applied versus file-persisted state and reports saved/unsaved files. | Verified workflow |
| 11 | `undo_edit` | Revert a recent MCP edit. | Returns reverted scope/current state and explains conflicts with subsequent user edits. | Verified workflow |
| 12 | `get_resource` | Read resource properties and sharing relationships. | Reports nested properties, shared users, locations and import-generated status to support local-versus-shared decisions. | Verified workflow |
| 13 | `create_resource` | Create and attach an independent resource. | Accepts type, initial values, target and save intent; returns the resource and attachment location for reuse. | Verified workflow |
| 14 | `update_resource` | Update resource properties. | Distinguishes per-node overrides from shared-source edits and reports affected targets and import persistence. | Verified workflow |
| 15 | `read_script` | Read current code and symbol locations. | Includes unsaved editor code, requested file/function/range, positions and edit state. | Verified workflow |
| 16 | `create_script` | Create a script or shader file. | Returns created code, diagnostics and actual attachment (node for script, material for shader). | Verified workflow |
| 17 | `edit_script` | Modify a code range and obtain diagnostics. | Applies against current content safely when source changed/unsaved; returns exact result, diagnostics and runtime-apply state. | Verified workflow |
| 18 | `update_signals` | Add or remove signal connections. | Returns actual connection state and required code changes, supporting create-handler-connect workflows. | Verified workflow |
| 19 | `get_animation` | Read animation tracks/keys or animation graphs. | Returns targets, keys, states, transitions, blend links and editable parameter paths. | Verified workflow |
| 20 | `edit_animation` | Create or edit animation tracks and keys. | Supports length, loop, property/transform/method tracks; reports scope and import persistence. | Verified workflow |
| 21 | `edit_animation_graph` | Configure animation states, transitions and blending. | Returns graph, animation links and real parameter paths for state machines, blend trees/spaces and conditions. | Verified workflow |
| 22 | `preview_animation` | Inspect a pose/frame at a specified time. | Returns pose and rendered view without unintentionally persisting preview changes to the scene. | Verified workflow |
| 23 | `get_tilemap` | Read cells and available tiles/terrain. | Returns placed cells plus tile/terrain identifiers directly usable by paint operations. | Verified workflow |
| 24 | `edit_tileset` | Edit TileSet sources, tiles, collision and terrain rules. | Supports atlas/source and tile definitions with collision/terrain links; detailed scope follows engine support and usage. | Verified workflow |
| 25 | `paint_tiles` | Paint cells, regions, patterns or terrain in bulk. | Returns changed cells and explains neighboring auto-connected terrain changes. | Verified workflow |
| 26 | `inspect_runtime` | Read live nodes and properties while the game runs. | Returns process-time nodes/values and observation time, distinct from scene-file values. | Verified workflow |
| 27 | `capture_viewport` | Capture the actual editor/game/3D viewport. | Returns an image with viewport and coordinate metadata usable for visual verification and input. | Verified workflow |
| 28 | `wait_for_condition` | Wait for a scene/node/property/signal condition. | Returns condition success and last observation, avoiding guessed fixed delays for loading/state changes. | Verified workflow |
| 29 | `get_diagnostics` | Read errors, warnings and execution logs. | Returns messages, locations and run context; distinguishes new failures from repeated existing errors. | Verified workflow |
| 30 | `sample_performance` | Measure runtime performance. | Returns supported metrics with units and measurement conditions; unsupported metrics are not fabricated. | Verified workflow |
| 31 | `run_scene` | Start a scene or main game. | Returns execution ID, actual run state and startup diagnostics, distinguishing request accepted from game running. | Verified workflow |
| 32 | `stop_game` | Stop the current test run. | Reports termination and cleanup, including injected input state. | Verified workflow |
| 33 | `send_input` | Send keyboard, mouse, touch or action input and observe effects. | Returns processed input plus subsequent state/view; supports input sequences and optional condition/capture checks. | Verified workflow |
| 34 | `inspect_debugger` | Read call stack and variables at a paused frame. | Returns stack and actual frame values, and identifies stale references after resume. | Verified workflow |
| 35 | `set_breakpoints` | Add, remove or change breakpoints. | Returns actual source locations and enabled state, interoperating with user breakpoints. | Verified workflow |
| 36 | `debug_control` | Pause, continue or step the debugger. | Returns debugger state and stopped location, distinguishing debugger breaks from ordinary game pause. | Verified workflow |
| 37 | `get_settings` | Read project settings, input actions and Autoloads. | Returns current values and available configuration information for the requested scope. | Verified workflow |
| 38 | `get_export_presets` | Inspect export targets and prerequisites. | Returns actual presets, target options and required export tooling. | Verified workflow |
| 39 | `import_assets` | Add or re-import external assets. | Verifies usable imported resources, reports retained edits and overwrite/disconnection follow-up items. | Verified workflow |
| 40 | `move_assets` | Move or rename assets while preserving references. | Returns move result, updated references and locations requiring review. | Verified workflow |
| 41 | `update_settings` | Change settings, input actions or Autoloads. | Returns applied values and save/restart implications. | Verified workflow |
| 42 | `export_build` | Export a verified project using a preset. | Returns actual artifacts, build result/errors and separates export success from artifact execution verification. | Verified workflow |

## Cross-cutting implementation requirements

- Center development on a Godot `EditorPlugin`; include user selection and unsaved edits, and connect changes to editor Undo/Redo.
- Use Python with the official MCP Python SDK for the server, typed GDScript `EditorPlugin` integration for editor operations, GDScript/debugger support for live game input/observation/capture, and DAP or the supported equivalent for breakpoints/stepping.
- Use `uv` to manage Python and dependencies. Keep required versions in `pyproject.toml` and `uv.lock`, and document environment setup, run and verification commands.
- Prefer MCP client ↔ server stdio and server ↔ plugin local WebSocket. Select a Python version compatible with the stable SDK and target Godot support.

## Installation and connection requirements

- Manage the server environment per user; install and enable the plugin per project, and record linked projects for discovery.
- Provide an HTTPS install address in README. Support shell entry points on macOS/Linux and, where Windows is supported, a PowerShell entry point; prepare `uv` and the required Python before running an interactive installer.
- Detect OS/architecture, Godot executable, and optional project; show detected values as editable defaults. MCP client registration remains client-owned.
- Recommend the newest stable MCP revision compatible with the detected Godot/platform. Show version, install location and settings; support edit/cancel and report when no compatible artifact exists.
- Verify the distribution, prepare the Python/dependency environment with `uv`, install the server and project plugin, and print a generic stdio `connect --home` command for client-side registration.
- Guide remaining activation steps, then verify the tool list and `get_context` versions/project connection. Distinguish installation completion from successful connection.
- Isolate server environments by product version, record the active executable and linked project index, and reuse the prepared environment for normal runs without changing dependencies.
- Default to user permissions, support answers through piped execution, and provide non-interactive/manual installation paths.
- Re-running the installer must support update/repair, refresh linked project plugins after validating the new environment, preserve unrelated project settings, and allow rollback or retry after failure.

## GitHub release and versioning requirements

- Maintain source in a public GitHub repository and distribute installable versions through GitHub Releases. Publish server/plugin/installer source, build files, license, issue path, and README guidance for features, support, installation, connection, use and updates.
- Release plugin and Python server packages with verified runtime/dependency information. Include Godot version, product version, platform, download location and integrity metadata readable by the installer.
- State supported Godot/MCP protocol versions, changes, limitations and any setting/call-shape impact; provide prior releases and rollback instructions.
- Make releases reproducible from product-version tags. Confirm packaged dependency metadata is honored by installation, then test a one-line install, connection and representative tools from a clean environment before publishing.
- Product version format is `v<godot-major>.<minor>.<patch>_<mcp-revision>`: `v4.7.2_0` targets Godot 4.7.2 and is its first MCP revision; same-engine fixes increment `_1`, `_2`, while a new engine starts at `_0`.
- Use that format in tags, release names and user-facing displays. Convert it at build time for Python metadata (`v4.7.2_0` → `4.7.2.0`) and manage one product version consistently. Keep revision numbering separate from stable/preview status; mark previews as GitHub Pre-releases, record MCP protocol version separately, and do not increment product revision for documentation-only edits.

## Godot update-response documentation

Document, against the actual repository after implementation, how to find upstream release/upgrade changes affecting this MCP, locate affected integration code/modules and tools, validate installation/editor editing/game integration on the new Godot with commands and pass criteria, update product/Python/dependency versions, package and publish, update existing installs and recover/rollback.

## Traceability note

The source labels this catalog as 42 tools. The inventory above contains exactly 42 unique tool names, numbered 1–42. Acceptance criteria are condensed from each tool's stated use, inputs, outputs and design notes; all 42 names appear in `tests/test_editor_integration.py`; both real-engine workflows pass on Linux x86_64.
