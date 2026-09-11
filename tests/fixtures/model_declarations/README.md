# Model declaration evidence

`v11-actual.json` is an unedited, programmatic export of all 45 Godot tool metadata entries from Codex CLI 0.154.0. A catalog-only server exposed the product TOOL_SPECS with execution disabled. The export used `ALL_TOOLS` and serialized its entries directly; declarations were not manually rewritten. `provenance.json` records the capture checksum and the input-contract checksum.

The checker compares the actual TypeScript input declarations for ten affected tools with the public JSON Schema: every declared field, required field, object, array, scalar and enum. It deliberately leaves JSON Schema bounds, path patterns, array length and exact-one object cardinality to server tests. Untyped tagged Godot values remain unconstrained as designed.

Tests weaken copies of the actual declarations in temporary directories to prove that erased shapes, optionalized required fields and unknown scalar leaves are detected. Those modified copies are synthetic tests, not client captures. `generated-calls.jsonl` and `generation-evidence.json` record a separate catalog-only model-call experiment with 18 accepted calls and one rejected resource selector that was corrected, covering all requested named cases; it does not establish runtime success or universal model reliability. Real Godot integration tests check execution separately.

Refresh the capture and provenance after input-contract changes. Run with an installed TypeScript compiler via `TSC=/path/to/tsc uv run pytest tests/test_model_declarations.py`.
