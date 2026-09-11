import pytest

from godot_mcp.bridge import ToolError
from godot_mcp.source_patch import (
    FilePatch,
    Hunk,
    apply_file_patch,
    build_plan,
    merge_source,
    parse_patch,
    revision,
)


def error_code(callable, *args):
    with pytest.raises(ToolError) as caught:
        callable(*args)
    return caught.value.code


def test_parse_add_and_update_sections():
    patch = """*** Begin Patch
*** Add File: res://new.gd
+extends Node
+
+func run():
+    pass
*** Update File: res://old.gd
@@ extends Node
 extends Node
-old()
+new()
*** End Patch"""
    files = parse_patch(patch)
    assert files == [
        FilePatch("res://new.gd", True, "extends Node\n\nfunc run():\n    pass\n"),
        FilePatch("res://old.gd", False, hunks=(Hunk("extends Node", ("extends Node", "old()"), ("extends Node", "new()")),)),
    ]


def test_exact_context_preserves_tabs_crlf_and_final_newline():
    file = parse_patch("*** Begin Patch\r\n*** Update File: res://x.gd\r\n@@ func f()\r\n \treturn 1\r\n-\treturn 2\r\n+\treturn 3\r\n*** End Patch\r\n")[0]
    assert apply_file_patch(file, "func f()\r\n\treturn 1\r\n\treturn 2\r\n") == "func f()\r\n\treturn 1\r\n\treturn 3\r\n"
    assert apply_file_patch(file, "func f()\r\n\treturn 1\r\n\treturn 2") == "func f()\r\n\treturn 1\r\n\treturn 3"


@pytest.mark.parametrize("patch", [
    "*** Begin Patch\n*** Update File: res://../x.gd\n@@\n x\n-x\n+y\n*** End Patch",
    "*** Begin Patch\n*** Update File: res://x.gd\n@@\n x\n-x\n+y\n*** Update File: res://x.gd\n@@\n a\n-a\n+b\n*** End Patch",
])
def test_path_traversal_and_duplicate_sections_rejected(patch):
    assert error_code(parse_patch, patch) == "INVALID_PATH" if "../" in patch else "INVALID_PATCH"


@pytest.mark.parametrize("patch", [
    "no patch",
    "*** Begin Patch\n*** Update File: res://x.gd\n*** End Patch",
    "*** Begin Patch\n*** Update File: res://x.gd\n@@\n+new\n*** End Patch",
])
def test_malformed_patch_and_contextless_insertion_rejected(patch):
    assert error_code(parse_patch, patch) == "INVALID_PATCH"


def test_end_of_file_append():
    patch = parse_patch("*** Begin Patch\n*** Update File: res://x.gd\n@@\n+tail\n*** End of File\n*** End Patch")[0]
    assert apply_file_patch(patch, "head\n") == "head\ntail\n"


def test_duplicate_context_requires_more_context():
    patch = parse_patch("*** Begin Patch\n*** Update File: res://x.gd\n@@\n-x\n+y\n*** End Patch")[0]
    assert error_code(apply_file_patch, patch, "x\nx\n") == "PATCH_CONTEXT"


def test_build_plan_attaches_revisions_and_merged_flag():
    base = "a\nb\n"
    snapshot = {"documents": [{"uri": "res://x.gd", "base_source": base, "source": "model\nb\nuser\n",
                                "revision": revision("model\nb\nuser\n"), "base_revision": revision(base),
                                "disk_revision": "disk"}]}
    file = parse_patch("*** Begin Patch\n*** Update File: res://x.gd\n@@\n-a\n+model\n b\n*** End Patch")[0]
    assert build_plan([file], snapshot)[0] == {"uri": "res://x.gd", "create": False,
        "source": "model\nb\nuser\n", "if_revision": revision("model\nb\nuser\n"),
        "disk_revision": "disk", "base_revision": revision(base), "merged": True}


def test_merge_independent_edits_preserves_both():
    assert merge_source("a\nb\nc\n", "a\nuser\nc\n", "a\nb\nmodel\n", "res://x.gd") == "a\nuser\nmodel\n"


def test_merge_identical_already_applied_change_does_not_duplicate():
    assert merge_source("a\n", "a\nmodel\n", "a\nmodel\n", "res://x.gd") == "a\nmodel\n"


@pytest.mark.parametrize(("current", "proposed"), [("a\nuser\nc\n", "a\nmodel\nc\n"),
                                                      ("a\nuser\nb\n", "a\nmodel\nb\n")])
def test_merge_overlaps_and_same_position_insertions_rejected(current, proposed):
    assert error_code(merge_source, "a\nb\n" if current.endswith("b\n") else "a\nc\n", current, proposed, "res://x.gd") == "REVISION_CONFLICT"


def test_merge_retains_current_final_newline_change():
    assert merge_source("a\nc\n", "a\nc", "b\nc\n", "res://x.gd") == "b\nc"
@pytest.mark.parametrize("base,current,proposed", [
    ("same\nsame\nend\n", "same\nend\n", "changed\nsame\nend\n"),
    ("same\nend\n", "same\nsame\nend\n", "changed\nend\n"),
])
def test_repeated_lines_at_trimmed_boundaries_are_ambiguous(base, current, proposed):
    with pytest.raises(ToolError) as error:
        merge_source(base, current, proposed, "res://repeated.gd")
    assert error.value.code == "MERGE_AMBIGUOUS"
