# Validation evidence — v4.7.2_1

Validated on Linux x86_64 with Godot 4.7.2, Python 3.13, the locked official MCP SDK 2.2.0, and protocol 2026-07-28.

| Layer | Command | Result |
| --- | --- | --- |
| Contracts, transport, discovery, installation transactions | `uv run pytest -q` | 56 passed; two engine tests opt-in |
| Real editor/game | `GODOT_MCP_INTEGRATION=1 uv run pytest tests/test_editor_integration.py -q` | Both workflows passed; all 42 tool names exercised |
| Clean versioned installation | `uv run scripts/verify_install.py` | Global stdio startup, empty-project context, link/discovery, 42-tool list, live node edit, reinstall reuse, repair passed |
| Lint and synchronized metadata | `uv run ruff check .`, `uv run scripts/sync_version.py --check`, `uv run scripts/generate_tool_docs.py --check` | Passed |

The editor workflow verifies unsaved node changes and undo; class metadata; local resource isolation; animation interpolation and pose restoration; state/blend graphs; imported atlas and tile collision editing; paint/undo; asset move/reference updates/undo; inherited node protection; script revision guards, diagnostics and signals; settings undo; and a real PCK export. The exported PCK is then launched with Godot and checked for script errors.

The game workflow verifies actual action/key input, observed property changes, signal waits, condition timeout, performance sampling and PNG capture. It stops/restarts the game at a GDScript breakpoint, reads the health variable, steps, rejects stale frame handles, clears MCP breakpoints, and continues. Screenshot pixels are inspected separately from the PNG signature/dimension checks.

The clean installer check runs the installed executable without source `PYTHONPATH`, from a directory outside the Godot project. It verifies a project-independent registration before linking a project, a failed connection before the editor opens, and a successful connection afterwards. Transaction unit tests verify rollback restores the active executable record, plugin, project settings, local linking record, project index, and client configuration, including recovery after registration failure.

These are representative acceptance workflows, not exhaustive tests of every node/resource type, exporter or input device. macOS, Windows and Linux ARM64 native runtime validation remains outstanding. Native executable exports require the matching export templates; the automated export acceptance uses a PCK, which does not require templates. Release bootstrap integrity and installation are also checked against the published GitHub artifacts before final delivery.

The v4.7.2_1 installer follow-up adds eight checks for detection, explicit paths, fallback input, noninteractive failure, and child-process environment isolation. A real source-bootstrap installation with conflicting inherited environment variables completed with no uv warnings and no Godot path prompt; its environment override did not create or modify the unrelated target.
