#!/usr/bin/env python3
"""Check actual client TypeScript inputs against the public JSON Schema contract."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from godot_mcp.catalog import SPECS

TOOLS = tuple(SPECS)


def extract_declaration(payload: list[dict], tool_name: str) -> str:
    entry = next((item for item in payload if item.get("name") == tool_name), None)
    if entry is None:
        raise ValueError(f"missing declaration for {tool_name}")
    text = entry.get("description", "")
    start = text.find("```ts")
    end = text.find("```", start + 5) if start >= 0 else -1
    if start < 0 or end < 0:
        raise ValueError(f"missing fenced TypeScript declaration for {tool_name}")
    return text[start + len("```ts"):end].strip()


PRELUDE = r"""
declare type CallToolResult<T = unknown> = { content: unknown[]; structuredContent?: T; };
type Assert<T extends true> = T;
type NN<T> = Exclude<T, null | undefined>;
type IsAny<T> = 0 extends (1 & T) ? true : false;
type Known<T> = IsAny<T> extends true ? false : [T] extends [never] ? false : unknown extends T ? false : true;
type Field<T, K extends PropertyKey> = K extends keyof NN<T> ? NN<T>[K] : never;
type Item<T> = NN<T> extends ReadonlyArray<infer I> ? I : never;
type MapValue<T> = NN<T> extends Record<string, infer V> ? V : never;
type Has<T, K extends PropertyKey> = K extends keyof NN<T> ? true : false;
type RequiredField<T, K extends PropertyKey> = K extends keyof NN<T> ? ({} extends Pick<NN<T>, K> ? false : true) : false;
type ObjectShape<T> = Known<NN<T>> extends true ? (NN<T> extends object ? (NN<T> extends readonly unknown[] ? false : true) : false) : false;
type ArrayShape<T> = Known<NN<T>> extends true ? (NN<T> extends readonly unknown[] ? true : false) : false;
type Scalar<T, E> = Known<NN<T>> extends true ? ([NN<T>] extends [E] ? ([E] extends [NN<T>] ? true : false) : false) : false;
"""


def shape_assertions(schema: dict, expression: str, path: str, checks: list[str]) -> None:
    """Compare only constraints TypeScript can carry: fields, requiredness, types.

    Bounds, patterns and exact-one/minItems cardinality are JSON Schema checks.
    Untyped Godot VALUE payloads intentionally remain unconstrained.
    """
    def check(predicate: str, label: str = path) -> None:
        checks.append(f"type Check{len(checks)} = Assert<{predicate}>; // {label}")

    kind = schema.get("type")
    if kind == "object":
        check(f"ObjectShape<{expression}>")
        for key, child in schema.get("properties", {}).items():
            quoted = json.dumps(key)
            check(f"Has<{expression}, {quoted}>", path + "." + key)
            if key in schema.get("required", []):
                check(f"RequiredField<{expression}, {quoted}>", path + "." + key + " required")
            shape_assertions(child, f"Field<{expression}, {quoted}>", path + "." + key, checks)
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict) and additional.get("type"):
            shape_assertions(additional, f"MapValue<{expression}>", path + ".*", checks)
    elif kind == "array":
        check(f"ArrayShape<{expression}>")
        shape_assertions(schema.get("items", {}), f"Item<{expression}>", path + "[]", checks)
    elif kind in {"string", "integer", "number", "boolean"}:
        expected = " | ".join(json.dumps(value) for value in schema["enum"]) if "enum" in schema else ("number" if kind == "integer" else kind)
        if "const" in schema:
            expected = json.dumps(schema["const"])
        check(f"Scalar<{expression}, {expected}>")


def build_probe(payload: list[dict]) -> tuple[str, int]:
    source = PRELUDE
    checks: list[str] = []
    for index, name in enumerate(TOOLS):
        declaration = extract_declaration(payload, f"mcp__godot__{name}")
        source += declaration.replace("declare const tools:", f"declare const tool{index}:", 1) + "\n"
        alias = f"Args{index}"
        source += f"type {alias} = Parameters<typeof tool{index}.mcp__godot__{name}>[0];\n"
        shape_assertions(SPECS[name]["inputSchema"], alias, name, checks)
    return source + "\n".join(checks) + "\n", len(checks)


def compile_declarations(payload: list[dict], tsc: str) -> int:
    source, count = build_probe(payload)
    with tempfile.TemporaryDirectory(prefix="model-declaration-check-") as directory:
        path = Path(directory) / "declarations.ts"
        path.write_text(source)
        result = subprocess.run([tsc, str(path), "--noEmit", "--strict", "--skipLibCheck"], text=True, capture_output=True)
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        if result.returncode == 0:
            print(f"Verified {count} field, requiredness and type assertions across {len(TOOLS)} actual declarations.")
        return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declarations", type=Path, required=True)
    parser.add_argument("--tsc", required=True)
    parser.add_argument("--expect-fail", action="store_true")
    args = parser.parse_args()
    try:
        code = compile_declarations(json.loads(args.declarations.read_text()), args.tsc)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.expect_fail:
        return 0 if code != 0 else 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
