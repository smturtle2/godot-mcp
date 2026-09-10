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
