# v4.7.2_14

- Reacquire scene objects after activation, report the observed active scene, and perform inactive-scene edits and Undo in their owning scene. Resolve custom resource compatibility through script identity and inheritance.
- Avoid reopening scenes on script-only saves, retain a small save receipt across editor restarts, and allow explicit editor reload to be deferred. Surface editor errors beside actual mutation effects and direct historical-error recovery to `get_logs`.
- Capture complete editor windows and frame 2D/3D scene content or selections. Preserve native pixels by default and share scene, time, crop, scale and coordinate metadata between editor and game captures.
- Report the active tool and phase on busy responses. Remove repeated source comparisons from routine runtime responses and restrict explicit comparisons to launch dependencies and observed runtime scripts.
- Allow deletion previews while a game is running and add explicit `find_assets(mode="list")` with optional shallow traversal.

The original terrain-save crash has not been reproduced or attributed; the save changes reduce unnecessary re-entry and preserve recovery evidence. Existing checks and CI remain small.

# v4.7.2_13

- Add `delete_assets` with a required preview/apply plan for files and folders. Plans include UID/import sidecars, current source revisions, affected editor state, and remaining references. Changed targets or references invalidate the plan; explicit `include_unsaved` and `references: "allow_broken"` keep destructive choices visible.
- Default to recoverable deletion with project-local durable records. `restore_assets` and editor Undo restore files, sidecars, and unsaved source without knowingly replacing current files or UID owners. Recovery IDs remain discoverable through `get_context` after an editor restart.
- Support direct permanent deletion and `purge_deleted_assets` for permanently removing selected recovery records. Permanent mode has no recovery copy or Undo; purging invalidates the associated Undo and leaves live project assets alone.
- Report actual applied and remaining entries on partial failure, with filesystem effects separate from editor scan completion. Pending scans use the existing `get_operation_result` workflow. Resource inspection and deletion now share UID dependency resolution.

Verified the deletion/recovery lifecycle, partial failure reporting, and recovery across an editor restart in Godot 4.7.2 on Linux. Reference coverage remains explicit: dynamically assembled and out-of-project paths cannot be exhaustively discovered. The reduced CI workflow remains unchanged.

# v4.7.2_12

- **Breaking source contract:** replace `read_script`, `create_script` and `edit_script` with batch `read_scripts` and one `apply_script_changes` context patch. Add and Update share exact context matching, revision guards, retained read bases and conservative three-way merging. Conflicts preserve concurrent editor changes; preview returns the guarded plan without applying it. New sources remain unsaved drafts by default.
- Coordinate source changes, explicit persistence, snapshot validation, editor reload, typed script/shader attachments and signals in one source operation. Pending receipts retain an operation ID; `get_operation_result(wait_ms)` waits without repeating work. `resume_script_changes` revalidates repaired sources and continues unfinished phases without replaying the patch or successful bindings. Preserve per-document effects, save attempts and ordered Undo steps after failures.
- **Breaking diagnostics contract:** `get_diagnostics` reports current source validity and coverage; `get_logs` separately reads historical editor/runtime entries. Diagnostics run asynchronously and can reuse a bounded cache only when the complete project, unsaved source, live settings and compiler fingerprint still matches. Recheck validation after editor waits and before unfinished bindings.
- Search current editor buffers and drafts by file name, source content or symbol, with revisions and pagination. Retain read bases within 256 versions and 16 MiB; bound source continuations to 32, diagnostic jobs to 16 and validation cache entries to eight/16 MiB. Pending source, diagnostic and import work appears in `get_context`.
- **Breaking launch contract:** `run_scene` uses explicit `save_uris`, optional revision guards and `restart`; remaining unsaved state blocks startup. Record startup source files through an editor/game handshake and report current runtime source provenance, changed files and restart requirements. Startup evidence does not prove executed behavior. Settle the previous debugger session before restarting.
- Keep patch parsing and merging in Python, editor source state in the source store, source continuations and diagnostics with their own owners, and startup manifests shared by the editor and runtime. Document the current workflow without legacy source adapters.
- Remove the client-specific declaration audit and captured metadata fixtures. Keep automatic checks small; run full Godot and installation checks manually, and avoid repeating main branch checks in the tag release workflow.

Refresh MCP tools after updating. Linux x86_64 editor workflows are supported; end-to-end game-development usability and model tool-selection behavior have not been verified for this release.

# v4.7.2_11

- **Breaking input contract:** select named payloads for script changes, runtime events and conditions, node sources, animation tracks/keys, and TileSet operations. Resource reads use `{uri}` or `{node:{scene,path,property}}`; resource mutations select `{local:{scene,path,property}}` or `{shared:<resource selector>}`. Required fields stay inside their selected payloads, and the same JSON Schema enforces exactly one choice before editor calls.
- **Breaking document response contract:** `create_script`, `edit_script`, `apply_script_changes`, and `save_documents` return compact receipts with an operation ID, outcome, per-URI effects and validation summary. Partial results retain failed phases, conflicts, executable recovery arguments, persistence boundaries and applicable Undo scope.
- Add `get_operation_result(operation_id)` as the 45th tool. It reads the detailed operation-time snapshot without repeating a mutation and reports current Undo eligibility separately. Document diagnostics, ordered save attempts and snapshot metadata are retained here instead of repeated in ordinary mutation responses.
- Share bounded result retention across document operations and imports: 64 records and 16 MiB of serialized results per editor session, evicting completed records before pending ones. Missing, expired and temporarily unavailable results return explicit errors. Import execution and file journals remain with their domain owner, capped at 32 pending imports.
- Shorten common instructions from 1,106 to 358 characters. Verify actual model declarations from Codex CLI 0.154.0 alongside strict schemas, generated arguments and real Godot behavior; TypeScript payload requirements and JSON Schema choice cardinality are checked separately.
- Preserve JSON integer-valued atlas IDs and use native TileData direction checks when setting or clearing terrain peering bits.
- Document clean current contracts as a development principle: backward compatibility is not a project goal. Keep one public input contract, canonical result owner and explicit compact projection, without superseded adapters or detail switches.

Validated with 130 unit tests, 33 real Godot integration cases, 766 actual model-declaration assertions, generated-call schema validation, and isolated installation, reinstall, repair and stdio checks on Linux x86_64.

# v4.7.2_10

- Publish complete object variants for structured tool inputs while preserving optional project selection and default TileSet node scope. Reject mixed resource selectors in both schemas and the editor before mutation.
- Track native editor buffer changes and saved revision baselines. Block source and scene saves on external changes or unknown baselines, and protect unsaved MCP drafts during filesystem operations.
- Preserve mouse button state across input batches and releases, and transform capture-relative movement along with positions. Use JSON-safe integer ranges for diagnostic and runtime counters.
- Report input condition errors, requested condition timeouts and capture failures as partial MCP errors while retaining applied effects and recovery guidance. Apply diagnostic kind filters before pagination without changing source validity.
- Retain asset import operation IDs, phases and file journals through timeout or partial writes. Query progress through `get_context(scope="operations")`; register guarded undo after import completion and preserve externally changed files.
- Share snapshot traversal and exclusions, skip unrelated symlinks, and report unavailable validation for excluded dependencies. Collect bounded stdout/stderr bytes before UTF-8 decoding.
- Share property and script attachment compatibility checks. Return executable retry arguments for script and shader attachment failures, and document state, conflict and recovery behavior.

Validated with 80 unit tests, 27 real Godot integration cases, and isolated installation, reinstall, repair and stdio checks on Linux x86_64. Refresh MCP tools after updating; the source schemas and stdio payloads are verified, while client-specific model schema rendering still requires a reconnect check. Native HiDPI/stretch and other operating systems remain unverified.

# v4.7.2_9

- Preserve canonical script resource identity across creation, attachment, editing, and scene saving.
- Report source validation, partial completion, persistence, and undo scope explicitly; incomplete operations set MCP `isError` while preserving successful steps.
- Add `apply_script_changes` for related sources with revision preflight, coherent validation of unsaved dependencies, draft support, and one editor undo operation. Support whole-source `edit_script` replacements.
- Validate fresh compiler snapshots instead of stale per-file caches; detect invalid shaders and report unavailable/pending checks honestly.
- Simplify input schemas and tool descriptions. **Contract changes:** `create_nodes` now uses flat `key`/`parent_key` records; `get_scene` defaults to structure and `properties: []` means no properties. Refresh the client's tools after updating.
- Recommend MCP editing while Godot is open, explaining unsaved-state, undo, and reload concerns without blocking direct editing.

# v4.7.2_8

- Skip NUL when escaping response control characters, avoiding Godot's `String.chr(0)` error on every MCP request.
- Add an editor integration regression check for unexpected NUL diagnostics.

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
