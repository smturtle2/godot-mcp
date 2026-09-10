# Implementation research

Investigated before implementation on 2026-09-11. The development brief defines
the intended workflows; official specifications and executable API probes decide
the implementation. Example JSON in the brief is illustrative.

## Verified baseline

- [Godot archive](https://godotengine.org/download/archive/4.7.2-stable/) lists
  4.7.2 stable. The local executable reports `4.7.2.stable.arch_linux.ed1daf0bf`.
- [EUPL v1.2 English text](https://joinup.ec.europa.eu/sites/default/files/custom-page/attachment/2020-03/EUPL-1.2%20EN.txt)
  is the authoritative license text used by this repository; the package metadata
  identifies the project as `EUPL-1.2`.
- [MCP's July specification](https://blog.modelcontextprotocol.io/posts/2026-07-28/)
  introduces per-request protocol metadata. Do not implement a handwritten
  initialize-only protocol loop.
- [Official Python SDK](https://py.sdk.modelcontextprotocol.io/) documents v2.
  PyPI metadata was checked directly: stable `mcp==2.2.0`, Python >=3.10.
  This project chooses Python >=3.11 and develops with 3.13.
- [Low-level SDK](https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/)
  accepts explicit tool schemas and constructor handlers. Its validation is the
  application's responsibility. Use JSON Schema 2020-12 and SDK result types.
  Introspection confirms `Server.run(read, write, initialization_options)` is the
  stdio entry point; a guessed `run_stdio` method does not exist.

## Editor and document design

[EditorPlugin](https://docs.godotengine.org/en/4.7/classes/class_editorplugin.html),
[EditorInterface](https://docs.godotengine.org/en/4.7/classes/class_editorinterface.html),
and [EditorUndoRedoManager](https://docs.godotengine.org/en/4.7/classes/class_editorundoredomanager.html)
are the integration boundary. Read live scene roots; do not parse saved TSCN text
as a substitute for the user's unsaved scene. Stage and validate edits before
committing an editor history action. Reject stale undo references after user edits.

[ScriptEditor](https://docs.godotengine.org/en/4.7/classes/class_scripteditor.html)
exposes open scripts, current editor, and unsaved files.
[ScriptEditorBase](https://docs.godotengine.org/en/4.7/classes/class_scripteditorbase.html)
exposes a base text editor, but no script-resource getter. The
[tagged editor source](https://github.com/godotengine/godot/blob/4.7.2-stable/editor/script/script_editor_plugin.cpp)
shows that open-script and open-editor arrays have different filtering. Do not
zip those arrays blindly. Select a script through the public editor interface,
read its CodeEdit buffer, then restore the previous script. Guard edits using a
content hash and use explicit one-based, end-exclusive text ranges.

[Resource](https://docs.godotengine.org/en/4.7/classes/class_resource.html)
sharing requires explicit node-local versus shared mutations. Duplicate a resource
for a node-local edit; preserve original identity for a shared edit. Imported
resources must be detached into authored resources to preserve changes across
reimport. Report sharing scope and persistence rather than promising preservation
of edits inside regenerated imports.

The local `ClassDB.class_get_method_list` probe confirmed:

- Open roots and unsaved-scene APIs are present in the target engine.
- FileSystemDock has no public asset-move method. Moving assets therefore needs
  a staged file operation plus explicit dependency/reference reconciliation.
- AnimationNodeStateMachine has indexed transition getters, not a guessed
  `get_transition_list`. Blend-tree connections are represented by resource
  properties and the public connect/disconnect methods.

## Runtime and debugging

[EditorDebuggerPlugin](https://docs.godotengine.org/en/4.7/classes/class_editordebuggerplugin.html),
[EditorDebuggerSession](https://docs.godotengine.org/en/4.7/classes/class_editordebuggersession.html),
and [EngineDebugger](https://docs.godotengine.org/en/4.7/classes/class_enginedebugger.html)
provide namespaced custom messages between the editor and the actual game.
Use a debug-only helper and runtime handshake. A started editor debugger session
alone is not proof that the helper can observe the game. Retain run IDs and
reject observations from prior runs.

[Input](https://docs.godotengine.org/en/4.7/classes/class_input.html) provides
`parse_input_event` for real input propagation. Timestamp sequences, bounded
condition waits, viewport coordinate metadata, and releases for held input make
playtests reproducible. Captures come from actual textures after rendering;
headless mode must return a renderer error rather than a fabricated screenshot.

[External-editor DAP documentation](https://docs.godotengine.org/en/4.7/tutorials/editor/external_editor.html)
and the [Godot DAP parser](https://github.com/godotengine/godot/blob/4.7.2-stable/editor/debugger/debug_adapter/debug_adapter_parser.cpp)
establish port 6006 (configurable), Content-Length framing, and a single main
thread. Attach needs an active editor-launched game. Launch completion is deferred
until configurationDone. Stack/scopes/variables can arrive asynchronously.
Use pause, continue, next and stepIn; stepOut is not implemented by this target.
Preserve user breakpoints when changing MCP-owned breakpoints and invalidate frame
handles on resume. Runtime pause and debugger suspension are different states.

[Logger](https://docs.godotengine.org/en/4.7/classes/class_logger.html) callbacks
may run on other threads. Buffer messages behind a Mutex, never log recursively,
and drain on the main thread with cursors/revisions for diagnostics.

## Animation and tiles

[Animation](https://docs.godotengine.org/en/4.7/classes/class_animation.html)
has separate value/position/rotation/scale/method tracks. Preview must use the
appropriate interpolation API and restore scene values; method tracks must not
execute as a side effect of inspection.
[AnimationNodeBlendTree](https://docs.godotengine.org/en/4.7/classes/class_animationnodeblendtree.html)
and [state machines](https://docs.godotengine.org/en/4.7/classes/class_animationnodestatemachine.html)
support authored animation graphs.
[TileSet](https://docs.godotengine.org/en/4.7/classes/class_tileset.html) uses source
IDs, which need not equal their indices.
[TileSetAtlasSource](https://docs.godotengine.org/en/4.7/classes/class_tilesetatlassource.html)
uses Vector2i tile size in create_tile. Stage tile/graph changes on a duplicate,
then commit once. Compare cell states before/after terrain painting, including
neighbor cells changed by automatic connections.

## Installation and release

[uv sync](https://docs.astral.sh/uv/concepts/projects/sync/) and exported locked
requirements allow version-isolated installations with immutable dependencies.
Run the installed executable directly; do not resolve packages at every MCP start.
[Python version rules](https://packaging.python.org/en/latest/specifications/version-specifiers/)
map product `v4.7.2_0` to package `4.7.2.0`.
[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
provide tag-linked assets and release status. Build checksum manifests, verify
downloads, stage replacements, and retain rollback data. Preserve unrelated
client config and project settings; distinguish installed from actually connected.

## README research

Reviewed primary READMEs for [uv](https://github.com/astral-sh/uv),
[MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), and
[Godot](https://github.com/godotengine/godot). Apply a recognizable hero, a short
outcome statement, factual badges, an early copyable setup path, a concrete
workflow example, and compact documentation links. Do not invent stars,
downloads, benchmarks, or supported platforms. Use the user-provided blue hero
unchanged; any new raster illustration should match its blue illustrated style.

## Verification plan

Real-engine tests will cover all tool families, unsaved edits and save/undo,
resource sharing, script conflicts, animation interpolation/graphs, tile terrain
neighbors, input-driven scene transitions, screenshots, metrics, DAP suspension,
asset reconciliation, export, and a clean packaged install. Schema/transport and
installer failure paths receive unit tests. Cross-platform claims depend on CI
results; unsupported features are documented explicitly.

## Installer follow-up: automatic Godot detection and uv isolation

The [Godot 4.7 command-line tutorial](https://docs.godotengine.org/en/4.7/tutorials/editor/command_line_tutorial.html) documents PATH usage, `--version`, and the macOS `Godot.app/Contents/MacOS/Godot` executable. Discovery checks PATH and bounded common application directories, validates the candidate, and prompts only on failure. Portable installations elsewhere can use `--godot`.

The [uv environment reference](https://docs.astral.sh/uv/reference/environment/) and [project environment documentation](https://docs.astral.sh/uv/concepts/projects/config/#project-environment-path) explain environment targeting and package linking. Installer child processes discard inherited `VIRTUAL_ENV`/`UV_PROJECT_ENVIRONMENT` and explicitly use `--link-mode copy`. This fixes the observed environment-mismatch and cross-filesystem hardlink fallback warnings without changing user-global settings or hiding other diagnostics.
