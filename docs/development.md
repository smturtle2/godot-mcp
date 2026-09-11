# Development

## Design principles

Choose the clearest, most coherent implementation for the current requirements. Backward compatibility is not a project goal. When a contract changes, remove superseded interfaces, aliases, adapters, and duplicated execution paths.

Keep one authoritative contract and give each responsibility a clear owner. Fix causes in their owning components, consolidate fragmented responsibilities, and separate mixed concerns. Update implementation, schemas, tests, and documentation together; document intentional breaking changes and verify runtime behavior.

## Checks

From the repository root:

```sh
uv sync --frozen
uv run pytest -m 'not integration'
uv run ruff check .
uv run scripts/sync_version.py --check
uv run scripts/generate_tool_docs.py --check
```

Real editor tests require the supported Godot version and an X11 display for viewport capture:

```sh
GODOT_MCP_INTEGRATION=1 uv run pytest -m integration
uv run scripts/verify_install.py
```

The installation check covers initial setup, MCP plugin installation, live editing, stable commands, reinstall reuse, and repair. It uses an isolated installation without changing the user's PATH.

Pushes and pull requests run unit tests, lint, and version/document synchronization checks. Full Godot integration and clean installation checks run only when the Verify workflow is started manually. Tag releases build a draft without repeating the main branch checks.

## Runtime design

```text
MCP client → stdio server → authenticated WebSocket → Godot EditorPlugin
                    └── install_plugin → project files and plugin activation
```

The client owns server startup and shutdown. The Python server validates tool arguments and selects a project; the plugin owns live scenes, unsaved state, editor history, and game operations. `install_plugin` and CLI `init` share the transactional installer and work before an editor connection exists.

`source_patch.py` parses context patches and conservatively merges retained read bases with current text. `source_tools.py` prepares a plan from an editor snapshot and submits it with revision and editor-session guards; the bridge remains transport only. `source_store.gd` owns current editor buffers, drafts and retained bases. `documents.gd` owns document access and explicit saves, while `source_operations.gd` coordinates source, persistence, validation, reload and binding phases.

`apply_script_changes`, `resume_script_changes` and `save_documents` use the canonical document result owned by `document_result.gd`. `result_projection.py` selects compact receipt fields, while shared `operation_records.gd` serializes inert operation-time snapshots. `get_operation_result` reports that snapshot plus current Undo eligibility, continuation availability and runtime provenance. Reading or waiting for a result never repeats a mutation. `catalog.py` defines public schemas; named input choices are strict JSON Schema objects with exactly one selected property, and server-side argument validation remains authoritative.

Keep applied effects with their domain owner and MCP `isError` mapping with the server. A pending operation is still running; a partial or failed mutation reports an error while preserving successful effects. A source verdict is current only when its full validation fingerprint remains unchanged. A saved source file and an applied but unsaved attachment are separate effects and must remain distinguishable.

The shared mutation boundaries have explicit owners:

| Responsibility | Owner |
|---|---|
| Public schemas and complete object variants | `catalog.py` |
| Context patch grammar and conservative text merging | `source_patch.py` |
| Source snapshot/plan submission and bounded result waiting | `source_tools.py` |
| Resource selectors, node ownership and scope validation | `resource_target.gd` |
| Property decoding, type checks and attachment compatibility | `property_edits.gd` |
| Editor buffers, drafts, saved baselines and retained read bases | `source_store.gd` |
| Current source reads and explicit save scope | `documents.gd` |
| Source phases, guarded continuations and binding steps | `source_operations.gd` |
| Current source content/symbol search and pagination | `source_search.gd` |
| Asynchronous current diagnostic jobs and coverage | `source_diagnostics.gd` |
| Snapshot fingerprints, compiler verdicts and bounded cache | `source_validation.gd` |
| Live project settings serialization and save baseline | `assets.gd` |
| Startup source file evidence shared by editor and game | `source_manifest.gd` |
| Launch save/revision preflight and runtime handshake | `runtime_tools.gd` |
| Bounded stdout/stderr byte collection and UTF-8 decoding | `process_output.gd` |
| Pending import execution phases and timeout continuation | `import_operations.gd` |
| Bounded detailed operation receipts | `operation_records.gd` |
| Compact result projection | `result_projection.py` |
| File before/after images and content guards | `file_journal.gd` |
| Applied effects, failures and pending stages in compound results | `operation_result.gd` |
| Injected input state and capture coordinate conversion | `runtime.gd` |
| Filtered log pagination for editor and runtime | `log_buffer.gd` |

Property plans decode values once and are consumed by their scene or resource owner. Source validation runs outside the editor mutation gate; source and dependency guards are checked again after waiting for the gate and before unfinished bindings. Resuming revalidates the repaired source state without replaying the patch or successful bindings. Read bases retain at most 256 versions and 16 MiB. Source continuations retain at most 32 running or blocked bundles, evicting blocked continuations when space is needed; diagnostic jobs are capped at 16. The validation cache retains at most eight entries and 16 MiB, keyed by the project files, unsaved overlays, live settings, requested sources and compiler executable. Cache reuse requires the full fingerprint to remain current.

Import continuations wait for importer quiescence and acquire the same mutation gate as requests before changing options or registering undo. The import manager retains only pending executions, capped at 32. Detailed operation receipts are inert shared records capped at 64 records and 16 MiB of serialized result bytes; completed records evict before pending records, oversized completed records expire, oversized pending records remain unavailable until republished, and editor restart loses all records. Operation IDs differ from Undo IDs.

Integration fixtures may instrument the copied plugin to control importer waits, partial writes and native editor buffer changes. Production code does not expose those test commands. Keep regression checks focused on observable behavior and meaningful failure boundaries. The catalog and server boundary own schema validation; refresh client tool metadata after contract changes.

See [state and recovery](workflows.md) for caller-visible conflict, timeout and retry behavior.

The stable launcher reads `active.json` to select the server environment. Retain its original runtime environment when maintaining installations. Setup must remain unattended and independent of client configuration files or Godot executable discovery.

Game launch requires explicit `save_uris` for unsaved documents; remaining unsaved state blocks launch. The child process reports a nonce-bound startup file manifest, and subsequent runtime observations report whether current sources still match. This evidence covers project settings, scripts, shaders, scenes and resource files; it does not prove which code executed or whether behavior is correct. Runtime references expire with their run; debugger references expire on resume. Headless viewport capture and DAP `step_out` are unsupported. Export checks artifact creation, not whether the exported application runs.

## Releases

`src/godot_mcp/version.py` is the version source. After changing versions or tool contracts, regenerate and run the checks above:

```sh
uv run scripts/sync_version.py
uv run scripts/generate_tool_docs.py
uv run scripts/build_release.py --output dist/release
```

Review archive contents and manifest hashes before publishing. Engine or protocol updates also require the integration suite and clean installation check. Update dependencies with `uv lock` when needed. Native validation beyond Linux x86_64 remains pending.
