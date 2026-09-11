"""Context patches and conservative three-way text merging, without filesystem I/O.

The editor supplies the retained base and current text. This module only plans
new text; Godot checks the current revisions again before applying that plan.
"""
from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath

from .bridge import ToolError

MAX_FILES = 100
MAX_SOURCE_BYTES = 1_000_000
MAX_PLAN_BYTES = 8 * 1024 * 1024
MAX_LINES = 20_000
MAX_DIFF_WORK = 4_000_000


def revision(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def source_uri(value: str) -> str:
    relative = value.removeprefix("res://")
    parts = relative.split("/")
    if (not value.startswith("res://") or "\\" in relative or "\0" in relative
            or any(part in {"", ".", ".."} for part in parts)
            or ":" in relative or PurePosixPath(relative).suffix not in {".gd", ".gdshader"}):
        raise ToolError("INVALID_PATH", "Patch paths must be .gd or .gdshader res:// paths without traversal.",
                        {"uri": value})
    return value


@dataclass(frozen=True)
class Hunk:
    anchor: str
    before: tuple[str, ...]
    after: tuple[str, ...]
    end: bool = False


@dataclass(frozen=True)
class FilePatch:
    uri: str
    create: bool
    source: str = ""
    hunks: tuple[Hunk, ...] = ()


def _check_size(source: str, uri: str) -> None:
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES or source.count("\n") > MAX_LINES:
        raise ToolError("SOURCE_LIMIT", "A source is limited to 1,000,000 UTF-8 bytes and 20,000 lines.",
                        {"uri": uri})


def parse_patch(patch: str) -> list[FilePatch]:
    """Parse one apply_patch-style Add/Update patch; no guessing or whitespace fuzz."""
    if "\0" in patch:
        raise ToolError("INVALID_PATCH", "A patch cannot contain NUL bytes.")
    lines = patch.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) < 3 or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise ToolError("INVALID_PATCH", "Use *** Begin Patch and *** End Patch around Add/Update File sections.")
    files: list[FilePatch] = []
    seen = set()
    index = 1

    def fail(message: str):
        raise ToolError("INVALID_PATCH", message, {"patch_line": index + 1})

    while index < len(lines) - 1:
        header = lines[index]
        create = header.startswith("*** Add File: ")
        if not create and not header.startswith("*** Update File: "):
            fail("Expected *** Add File: res://... or *** Update File: res://... .")
        uri = source_uri(header.split(": ", 1)[1])
        if uri in seen:
            fail("Combine all hunks for a source in one file section.")
        seen.add(uri)
        index += 1
        if create:
            added = []
            while index < len(lines) - 1 and not lines[index].startswith("*** "):
                if not lines[index].startswith("+"):
                    fail("Every line in an Add File section must begin with +.")
                added.append(lines[index][1:])
                index += 1
            source = "\n".join(added) + ("\n" if added else "")
            _check_size(source, uri)
            files.append(FilePatch(uri=uri, create=True, source=source))
        else:
            hunks = []
            while index < len(lines) - 1 and lines[index].startswith("@@"):
                header = lines[index]
                if header != "@@" and not header.startswith("@@ "):
                    fail("Use @@ or @@ followed by an exact context line.")
                anchor = header[3:] if header != "@@" else ""
                # Numbered unified-diff headers are a different dialect. A clear
                # error avoids accidentally interpreting a line range as text.
                if anchor.startswith(("-", "+")):
                    fail("Use context hunks (@@), without unified-diff line counts.")
                index += 1
                before, after = [], []
                changed = False
                while index < len(lines) - 1:
                    line = lines[index]
                    if line.startswith(("@@", "*** ")):
                        break
                    if not line or line[0] not in " +-":
                        fail("Each hunk line must begin with space (context), - (remove), or + (add).")
                    if line[0] in " -":
                        before.append(line[1:])
                    if line[0] in " +":
                        after.append(line[1:])
                    changed |= line[0] in "+-"
                    index += 1
                end = index < len(lines) - 1 and lines[index] == "*** End of File"
                if end:
                    index += 1
                if not changed:
                    fail("Each update hunk must add or remove source text.")
                if not before and not end:
                    fail("An insertion needs context, or *** End of File for an append.")
                hunks.append(Hunk(anchor, tuple(before), tuple(after), end))
            if not hunks:
                fail("An Update File section needs at least one @@ hunk.")
            files.append(FilePatch(uri=uri, create=False, hunks=tuple(hunks)))
        if len(files) > MAX_FILES:
            fail("A patch may change at most 100 sources.")
    if not files:
        fail("Provide at least one source change.")
    return files


def _lines(source: str) -> tuple[list[str], str, bool]:
    newline = "\r\n" if "\r\n" in source else "\n"
    # Bare CR is source text, not a line terminator in the patch language.
    normalized = source.replace("\r\n", "\n")
    values = normalized.split("\n")
    ended = normalized.endswith("\n")
    if ended:
        values.pop()
    if source == "":
        values = []
    return values, newline, ended


def apply_file_patch(file: FilePatch, base: str) -> str:
    if file.create:
        return file.source
    _check_size(base, file.uri)
    lines, newline, ended = _lines(base)
    planned: list[tuple[int, int, list[str]]] = []
    cursor = 0
    for number, hunk in enumerate(file.hunks, 1):
        start = cursor
        if hunk.anchor:
            anchors = [i for i in range(cursor, len(lines)) if lines[i] == hunk.anchor]
            if len(anchors) != 1:
                raise ToolError("PATCH_CONTEXT", "The hunk anchor must match exactly once in the base source.",
                                {"uri": file.uri, "hunk": number, "anchor": hunk.anchor,
                                 "matches": len(anchors)})
            start = anchors[0] + 1
        width = len(hunk.before)
        candidates = ([len(lines)] if not width else
                      [i for i in range(start, len(lines) - width + 1)
                       if tuple(lines[i:i + width]) == hunk.before])
        if hunk.end:
            candidates = [i for i in candidates if i + width == len(lines)]
        if len(candidates) != 1:
            raise ToolError("PATCH_CONTEXT", "The hunk must match exactly once; include more unchanged context.",
                            {"uri": file.uri, "hunk": number, "matches": len(candidates),
                             "expected_context": list(hunk.before[:12]), "base_revision": revision(base)})
        at = candidates[0]
        if planned and at == planned[-1][0] and at == planned[-1][1]:
            raise ToolError("PATCH_CONTEXT", "Combine insertions at the same position.", {"uri": file.uri})
        planned.append((at, at + width, list(hunk.after)))
        cursor = at + width
    for start, end, replacement in reversed(planned):
        lines[start:end] = replacement
    source = newline.join(lines) + (newline if ended and lines else "")
    _check_size(source, file.uri)
    return source


@dataclass(frozen=True)
class TextChange:
    start: int
    end: int
    replacement: tuple[str, ...]


def _changes(base: list[str], other: list[str], uri: str) -> list[TextChange]:
    # Trim common ends before bounding the quadratic worst case. Ordinary edits
    # in a large source remain cheap; widely rewritten/repetitive sources fail
    # explicitly instead of blocking the server for an unbounded diff.
    start = 0
    while start < min(len(base), len(other)) and base[start] == other[start]:
        start += 1
    end_base, end_other = len(base), len(other)
    while end_base > start and end_other > start and base[end_base - 1] == other[end_other - 1]:
        end_base -= 1
        end_other -= 1
    if (end_base - start) * (end_other - start) > MAX_DIFF_WORK:
        raise ToolError("MERGE_LIMIT", "Concurrent changes are too large to merge conservatively; read current source and create a fresh patch.",
                        {"uri": uri})
    left, right = base[start:end_base], other[start:end_other]
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    changes = [TextChange(a + start, b + start, tuple(other[c + start:d + start]))
               for tag, a, b, c, d in matcher.get_opcodes() if tag != "equal"]
    for change in changes:
        # Trimming equal ends can conceal duplicate-line insert/delete choices.
        # A change that can slide one line while producing the same text has
        # no unique provenance, even if the trimmed alignments agree.
        can_slide_left = (change.start > 0 and change.end > 0
                and (change.replacement[-1] if change.replacement else base[change.start - 1])
                == base[change.end - 1])
        can_slide_right = (change.start < len(base) and change.end < len(base)
                 and (change.replacement[0] if change.replacement else base[change.end])
                 == base[change.start])
        if can_slide_left or can_slide_right:
            raise ToolError("MERGE_AMBIGUOUS", "Repeated source text admits different edit positions; read current source and create a fresh patch.",
                            {"uri": uri})
    reverse = difflib.SequenceMatcher(None, list(reversed(left)), list(reversed(right)), autojunk=False)
    reverse_changes = [TextChange(end_base - b, end_base - a, tuple(other[end_other - d:end_other - c]))
                       for tag, a, b, c, d in reverse.get_opcodes() if tag != "equal"]
    if changes != list(reversed(reverse_changes)):
        raise ToolError("MERGE_AMBIGUOUS", "Repeated source text admits different edit alignments; read current source and create a fresh patch.",
                        {"uri": uri})
    return changes


def _overlap(first: TextChange, second: TextChange) -> bool:
    if first.start == first.end and second.start == second.end:
        return first.start == second.start
    if first.start == first.end:
        return second.start < first.start < second.end
    if second.start == second.end:
        return first.start < second.start < first.end
    return max(first.start, second.start) < min(first.end, second.end)


def merge_source(base: str, current: str, proposed: str, uri: str) -> str:
    """Merge independent line edits, preserving the editor text and line endings."""
    if current == base or current == proposed:
        return proposed
    if proposed == base:
        return current
    for source in (base, current, proposed):
        _check_size(source, uri)
    # Keep line endings and the final-newline bit in the comparison. This avoids
    # silently discarding an editor newline edit while merging a code change.
    base_lines = base.splitlines(keepends=True)
    current_lines = current.splitlines(keepends=True)
    proposed_lines = proposed.splitlines(keepends=True)
    user_changes = _changes(base_lines, current_lines, uri)
    model_changes = _changes(base_lines, proposed_lines, uri)
    combined = list(user_changes)
    for change in model_changes:
        same = False
        for user_change in user_changes:
            if change == user_change:
                same = True
                break
            if _overlap(change, user_change):
                raise ToolError("REVISION_CONFLICT", "The patch overlaps edits made since the source was read; read and reconcile this context.",
                                {"uri": uri, "base_revision": revision(base), "current_revision": revision(current),
                                 "base_start_line": min(change.start, user_change.start) + 1,
                                 "base_context": "".join(base_lines[max(0, min(change.start, user_change.start) - 2):max(change.end, user_change.end) + 2]),
                                 "editor_change": "".join(user_change.replacement),
                                 "patch_change": "".join(change.replacement)})
        if not same:
            combined.append(change)
    output = list(base_lines)
    for change in sorted(combined, key=lambda value: (value.start, value.end), reverse=True):
        output[change.start:change.end] = change.replacement
    result = "".join(output)
    _check_size(result, uri)
    return result


def build_plan(files: list[FilePatch], snapshot: dict) -> list[dict]:
    """Compile a captured editor snapshot into guarded source replacements."""
    captured = {item["uri"]: item for item in snapshot["documents"]}
    result = []
    total = 0
    for file in files:
        item = captured[file.uri]
        if file.create:
            source = file.source
            merged = False
        else:
            base = item["base_source"]
            proposed = apply_file_patch(file, base)
            source = merge_source(base, item["source"], proposed, file.uri)
            merged = item["revision"] != item["base_revision"]
        total += len(source.encode("utf-8"))
        if total > MAX_PLAN_BYTES:
            raise ToolError("SOURCE_LIMIT", "A source change plan is limited to 8 MiB.")
        result.append({"uri": file.uri, "create": file.create, "source": source,
                       "if_revision": item.get("revision"), "disk_revision": item.get("disk_revision"),
                       "base_revision": item.get("base_revision"), "merged": merged})
    return result
