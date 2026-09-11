import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from godot_mcp.catalog import TOOL_SPECS
from scripts.check_model_declarations import TOOLS, extract_declaration

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests/fixtures/model_declarations"
CURRENT = FIXTURES / "v12-actual.json"
TSC = os.environ.get("TSC") or shutil.which("tsc")


def test_capture_provenance_matches_actual_metadata_and_current_inputs():
    provenance = json.loads((FIXTURES / "provenance.json").read_text())
    payload = json.loads(CURRENT.read_text())
    assert len(payload) == provenance["tool_count"] == 45
    assert hashlib.sha256(CURRENT.read_bytes()).hexdigest() == provenance["capture_sha256"]
    contracts = {spec["name"]: spec["inputSchema"] for spec in TOOL_SPECS}
    digest = hashlib.sha256(json.dumps(contracts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert digest == provenance["input_contract_sha256"], "Refresh the actual client capture after changing inputs"
    for name in TOOLS:
        assert "declare const tools" in extract_declaration(payload, f"mcp__godot__{name}")
    with pytest.raises(ValueError, match="missing declaration"):
        extract_declaration(payload, "missing")


def compile_capture(path, *args):
    return subprocess.run(["uv", "run", "python", "scripts/check_model_declarations.py", "--declarations", str(path), "--tsc", TSC, *args], cwd=ROOT, text=True, capture_output=True)


@pytest.mark.skipif(TSC is None, reason="TypeScript compiler unavailable")
def test_actual_v12_declarations_preserve_all_declared_payload_fields_and_requirements():
    result = compile_capture(CURRENT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"across {len(TOOLS)} actual declarations" in result.stdout


@pytest.mark.skipif(TSC is None, reason="TypeScript compiler unavailable")
@pytest.mark.parametrize("old,new", [
    ("key: string;", "key?: string;"),
    ("key: string;", "key: unknown;"),
    ("key: string;", "key: any;"),
    ("key: string;", "key: {};"),
])
def test_weakened_copies_fail_real_type_assertions(tmp_path, old, new):
    payload = copy.deepcopy(json.loads(CURRENT.read_text()))
    event_tool = next(item for item in payload if item["name"] == "mcp__godot__send_input")
    assert old in event_tool["description"]
    event_tool["description"] = event_tool["description"].replace(old, new, 1)
    path = tmp_path / "synthetic-weakened.json"
    path.write_text(json.dumps(payload))
    result = compile_capture(path)
    assert result.returncode != 0 and "error TS" in result.stdout, result.stdout + result.stderr
    expected = compile_capture(path, "--expect-fail")
    assert expected.returncode == 0, expected.stdout + expected.stderr


@pytest.mark.skipif(TSC is None, reason="TypeScript compiler unavailable")
def test_erased_event_items_fail_shape_assertions(tmp_path):
    payload = json.loads(CURRENT.read_text())
    event_tool = next(item for item in payload if item["name"] == "mcp__godot__send_input")
    description, count = re.subn(r"events: Array<.*?>;", "events: unknown[];", event_tool["description"], count=1, flags=re.S)
    assert count == 1
    event_tool["description"] = description
    path = tmp_path / "synthetic-erased-items.json"
    path.write_text(json.dumps(payload))
    result = compile_capture(path)
    assert result.returncode != 0 and "error TS" in result.stdout, result.stdout + result.stderr
