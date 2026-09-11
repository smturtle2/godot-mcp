# Development

## Design principles

Choose the clearest, most coherent implementation for the current requirements. Backward compatibility is not a project goal. When a contract changes, remove superseded interfaces, aliases, adapters, and duplicated execution paths.

Keep one authoritative contract and give each responsibility a clear owner. Fix causes in their owning components, consolidate fragmented responsibilities, and separate mixed concerns. Update implementation, schemas, tests, and documentation together; document intentional breaking changes and verify runtime behavior.

## Checks

From the repository root:

```sh
uv sync --frozen
uv run pytest
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

## Runtime design

```text
MCP client → stdio server → authenticated WebSocket → Godot EditorPlugin
                    └── install_plugin → project files and plugin activation
```

The client owns server startup and shutdown. The Python server validates tool arguments and selects a project; the plugin owns live scenes, unsaved state, editor history, and game operations. `install_plugin` and CLI `init` share the transactional installer and work before an editor connection exists.

Source state belongs to `source_store.gd`, compiler snapshots to `source_validation.gd`, and edit/save orchestration to `documents.gd`. Single-file and batch edits share the same revision checks, live state, validation, and undo path.

The four document mutators return the canonical full result owned by `document_result.gd`. `result_projection.py` selects the compact receipt fields, while shared `operation_records.gd` serializes inert operation-time snapshots. `get_operation_result` reports that snapshot plus current Undo eligibility, computed by the plugin with the same checker used by actual undo. `catalog.py` defines the current output contract; named input choices are strict JSON Schema objects with exactly one selected property, and server-side argument validation remains authoritative. A fresh client capture is required to verify how an external model converter renders those nested payload types.

Keep document ownership separated: the Godot document layer decides what was applied and what failed; `result_projection.py` selects the compact receipt; the operation-record layer retains immutable detailed snapshots; the catalog owns public schemas; and the server owns MCP `isError` mapping. `get_operation_result` returns the operation-time snapshot and a separately computed current Undo status. Do not make clients infer a new verdict from a checked revision that differs from the document revision. A saved source file and an applied but unsaved attachment are separate effects and must remain distinguishable.

The shared mutation boundaries have explicit owners:

| Responsibility | Owner |
|---|---|
| Public schemas and complete object variants | `catalog.py` |
| Resource selectors, node ownership and scope validation | `resource_target.gd` |
| Property decoding, type checks and attachment compatibility | `property_edits.gd` |
| Editor buffer observation and its saved revision baseline | `source_store.gd` |
| Snapshot copy/fingerprint exclusions and compiler verdicts | `source_validation.gd` |
| Bounded stdout/stderr byte collection and UTF-8 decoding | `process_output.gd` |
| Pending import execution phases and timeout continuation | `import_operations.gd` |
| Bounded detailed operation receipts | `operation_records.gd` |
| Compact result projection | `result_projection.py` |
| File before/after images and content guards | `file_journal.gd` |
| Applied effects, failures and pending stages in compound results | `operation_result.gd` |
| Injected input state and capture coordinate conversion | `runtime.gd` |
| Filtered log pagination for editor and runtime | `log_buffer.gd` |

Property plans decode values once and are consumed by their scene or resource owner. Source compilation remains a document operation. Import continuations wait for importer quiescence and acquire the same mutation gate as requests before changing options or registering undo. The import manager retains only pending executions, capped at 32. Detailed operation receipts are inert shared records capped at 64 records and 16 MiB of serialized result bytes; completed records evict before pending records, oversized completed records expire, oversized pending records remain unavailable until republished, and editor restart loses all records. Operation IDs differ from Undo IDs.

Integration fixtures may instrument the copied plugin to control importer waits, partial writes and native editor buffer changes. Production code does not expose those test commands. Validate both successful results and partial results against their MCP output schemas. Schema tests verify the raw catalog and server boundary; rendering by an external client's schema converter requires a separate client reconnect check.

`scripts/check_model_declarations.py --declarations capture.json --tsc /path/to/tsc` compares actual client metadata against the public input schemas. The checked-in Codex CLI 0.154.0 capture contains all 45 tool declarations with checksums and provenance; 766 field, requiredness and type assertions cover ten affected tools. Synthetic weakened copies verify that erased shapes and optionalized required fields are caught. Set `TSC` or put `tsc` on PATH to enable compiler tests. JSON Schema still enforces bounds, path patterns, array lengths and exactly one named choice; those constraints do not survive as TypeScript types.

The separate catalog-only generation probe records 18 accepted calls and one rejected resource selector that the model corrected. Its saved arguments cover all six input events, four conditions, seven TileSet changes, script/node/animation variants and resource scopes. This validates generated arguments without executing Godot; it is separate from integration tests and does not establish universal model reliability. See [capture evidence](../tests/fixtures/model_declarations/README.md) for artifacts and limits.

See [state and recovery](workflows.md) for caller-visible conflict, timeout and retry behavior.

The stable launcher reads `active.json` to select the server environment. Retain its original runtime environment when maintaining installations. Setup must remain unattended and independent of client configuration files or Godot executable discovery.

Save explicitly before running a game. Runtime references expire with their run; debugger references expire on resume. Headless viewport capture and DAP `step_out` are unsupported. Export checks artifact creation, not whether the exported application runs.

## Releases

`src/godot_mcp/version.py` is the version source. After changing versions or tool contracts, regenerate and run the checks above:

```sh
uv run scripts/sync_version.py
uv run scripts/generate_tool_docs.py
uv run scripts/build_release.py --output dist/release
```

Review archive contents and manifest hashes before publishing. Engine or protocol updates also require the integration suite and clean installation check. Update dependencies with `uv lock` when needed. Native validation beyond Linux x86_64 remains pending.
