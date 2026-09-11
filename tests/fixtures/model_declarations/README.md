# Model declaration evidence

`v12-actual.json` is an unedited, programmatic export of all 45 Godot tool metadata entries from Codex CLI 0.154.0. A catalog-only server exposed the product TOOL_SPECS with execution disabled. The export used `ALL_TOOLS` and serialized its entries directly; declarations were not manually rewritten. `provenance.json` records the capture checksum and the input-contract checksum.

The checker verifies all 45 actual TypeScript input declarations against the public JSON Schema with 1,605 assertions covering declared fields, required fields, objects, arrays, scalars and enums. It deliberately leaves JSON Schema bounds, path patterns, array length and exact-one object cardinality to server tests. Untyped tagged Godot values remain unconstrained as designed.

Tests weaken copies of the actual declarations in temporary directories to prove that erased shapes, optionalized required fields and unknown scalar leaves are detected. Those modified copies are synthetic tests, not client captures. This evidence establishes declaration fidelity only; it does not measure tool selection, generated-call success or game-development usability. There is no model-call generation experiment for this contract. Real Godot integration tests check execution separately.

Refresh the capture and provenance after input-contract changes. Run with an installed TypeScript compiler via `TSC=/path/to/tsc uv run pytest tests/test_model_declarations.py`.
