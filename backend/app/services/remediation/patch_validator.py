"""Strict, non-mutating Unified Diff validation for snapshot files."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from .snapshot_paths import _normalize_relative_path, _safe_target, _snapshot_root
from .types import PatchValidationResult, _PatchHunk

from app.services.security_knowledge import SecurityKnowledgeRetriever, _redact_text


_HUNK_HEADER = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?: .*)?$"
)
_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
_BINARY_MARKERS = ("GIT binary patch", "Binary files ", "literal ", "delta ")
_DISALLOWED_METADATA = (
    "new file mode ",
    "deleted file mode ",
    "rename from ",
    "rename to ",
    "similarity index ",
    "dissimilarity index ",
)


def validate_unified_patch(
    snapshot_root: str | Path,
    finding_file_path: str,
    patch_diff: str,
    max_lines: int,
    max_chars: int,
) -> PatchValidationResult:
    """Validate an untrusted Unified Diff without ever applying it.

    The patch must target exactly ``finding_file_path`` under ``snapshot_root``
    and every old-side context/deletion line must match the immutable snapshot.
    """
    if not isinstance(patch_diff, str) or not patch_diff.strip():
        return _invalid("PATCH_EMPTY")
    if not isinstance(max_lines, int) or not isinstance(max_chars, int) or max_lines <= 0 or max_chars <= 0:
        return _invalid("PATCH_LIMIT_INVALID")
    if "\x00" in patch_diff:
        return _invalid("PATCH_BINARY")
    if len(patch_diff) > max_chars or len(patch_diff.splitlines()) > max_lines:
        return _invalid("PATCH_TOO_LARGE")
    if any(marker in patch_diff for marker in _BINARY_MARKERS):
        return _invalid("PATCH_BINARY")

    expected_path = _normalize_relative_path(finding_file_path, allow_diff_prefix=False)
    if expected_path is None:
        return _invalid("PATCH_FINDING_PATH_INVALID")

    parsed = _parse_patch(patch_diff, expected_path)
    if isinstance(parsed, str):
        return _invalid(parsed)
    target_path, hunks = parsed

    root = _snapshot_root(snapshot_root)
    if root is None:
        return _invalid("PATCH_SNAPSHOT_NOT_FOUND")
    target = _safe_target(root, target_path)
    if target is None:
        return _invalid("PATCH_TARGET_NOT_FOUND")

    return _validate_hunks_against_target(target, hunks, patch_diff)


def _invalid(*warning_codes: str) -> PatchValidationResult:
    return PatchValidationResult(False, None, tuple(dict.fromkeys(warning_codes)))


def _parse_patch(patch_diff: str, expected_path: str) -> tuple[str, tuple[_PatchHunk, ...]] | str:
    lines = patch_diff.splitlines()
    old_headers = [index for index, line in enumerate(lines) if line.startswith("--- ")]
    new_headers = [index for index, line in enumerate(lines) if line.startswith("+++ ")]
    if len(old_headers) > 1 or len(new_headers) > 1:
        return "PATCH_MULTIFILE"
    if len(old_headers) != 1 or len(new_headers) != 1:
        return "PATCH_FORMAT_INVALID"

    old_index = old_headers[0]
    new_index = new_headers[0]
    if new_index != old_index + 1:
        return "PATCH_FORMAT_INVALID"

    preamble_error = _validate_preamble(lines[:old_index], expected_path)
    if preamble_error:
        return preamble_error

    old_path = _header_path(lines[old_index], "--- ")
    new_path = _header_path(lines[new_index], "+++ ")
    if old_path is None or new_path is None:
        return "PATCH_PATH_INVALID"
    if old_path != new_path or old_path != expected_path:
        return "PATCH_PATH_MISMATCH"

    hunks: list[_PatchHunk] = []
    cursor = new_index + 1
    while cursor < len(lines):
        match = _HUNK_HEADER.fullmatch(lines[cursor])
        if match is None:
            return "PATCH_FORMAT_INVALID"
        old_start = int(match.group("old_start"))
        old_count = int(match.group("old_count") or "1")
        new_start = int(match.group("new_start"))
        new_count = int(match.group("new_count") or "1")
        if old_start < 1 or new_start < 1 or old_count < 1 or new_count < 1:
            return "PATCH_HUNK_RANGE_INVALID"

        cursor += 1
        hunk_lines: list[str] = []
        while cursor < len(lines) and not lines[cursor].startswith("@@ "):
            line = lines[cursor]
            if line == r"\ No newline at end of file":
                if not hunk_lines:
                    return "PATCH_FORMAT_INVALID"
            elif line.startswith((" ", "+", "-")):
                hunk_lines.append(line)
            else:
                return "PATCH_FORMAT_INVALID"
            cursor += 1

        hunk_error = _validate_hunk_shape(old_count, new_count, hunk_lines)
        if hunk_error:
            return hunk_error
        hunks.append(
            _PatchHunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                lines=tuple(hunk_lines),
            )
        )

    if not hunks:
        return "PATCH_FORMAT_INVALID"
    if not any(line.startswith(("+", "-")) for hunk in hunks for line in hunk.lines):
        return "PATCH_FORMAT_INVALID"
    return expected_path, tuple(hunks)


def _validate_preamble(lines: Iterable[str], expected_path: str) -> str | None:
    diff_headers = 0
    for line in lines:
        if not line:
            continue
        if any(line.startswith(marker) for marker in _BINARY_MARKERS):
            return "PATCH_BINARY"
        if any(line.startswith(marker) for marker in _DISALLOWED_METADATA):
            return "PATCH_FORMAT_INVALID"
        if line.startswith("index "):
            continue
        if line.startswith("diff --git "):
            diff_headers += 1
            if diff_headers > 1:
                return "PATCH_MULTIFILE"
            paths = line.removeprefix("diff --git ").split()
            if len(paths) != 2:
                return "PATCH_FORMAT_INVALID"
            left = _normalize_relative_path(paths[0], allow_diff_prefix=True)
            right = _normalize_relative_path(paths[1], allow_diff_prefix=True)
            if left is None or right is None:
                return "PATCH_PATH_INVALID"
            if left != expected_path or right != expected_path:
                return "PATCH_PATH_MISMATCH"
            continue
        return "PATCH_FORMAT_INVALID"
    return None


def _header_path(line: str, prefix: str) -> str | None:
    value = line.removeprefix(prefix).split("\t", maxsplit=1)[0].strip()
    return _normalize_relative_path(value, allow_diff_prefix=True)


def _normalize_relative_path(value: str, *, allow_diff_prefix: bool) -> str | None:
    if not isinstance(value, str):
        return None
    path = value.strip()
    if not path or path == "/dev/null" or "\x00" in path or "\\" in path:
        return None
    if allow_diff_prefix and path[:2] in {"a/", "b/"}:
        path = path[2:]
    if path.startswith("/") or path.startswith("~") or _DRIVE_PATH.match(path):
        return None
    parts = path.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return "/".join(parts)


def _validate_hunk_shape(old_count: int, new_count: int, hunk_lines: list[str]) -> str | None:
    if not hunk_lines:
        return "PATCH_FORMAT_INVALID"
    old_lines = sum(1 for line in hunk_lines if line.startswith((" ", "-")))
    new_lines = sum(1 for line in hunk_lines if line.startswith((" ", "+")))
    if old_lines != old_count or new_lines != new_count:
        return "PATCH_HUNK_COUNT_MISMATCH"
    if not any(line.startswith(" ") for line in hunk_lines):
        return "PATCH_NO_CONTEXT"
    return None


def _validate_hunks_against_target(
    target: Path,
    hunks: tuple[_PatchHunk, ...],
    patch_diff: str,
) -> PatchValidationResult:
    expected_lines: dict[int, str] = {}
    previous_end = 0
    for hunk in hunks:
        if hunk.old_start <= previous_end:
            return _invalid("PATCH_HUNK_RANGE_INVALID")
        source_line = hunk.old_start
        for line in hunk.lines:
            if line.startswith((" ", "-")):
                prior = expected_lines.get(source_line)
                content = line[1:]
                if prior is not None and prior != content:
                    return _invalid("PATCH_HUNK_RANGE_INVALID")
                expected_lines[source_line] = content
                source_line += 1
        previous_end = source_line - 1

    actual_lines: dict[int, str] = {}
    try:
        with target.open("r", encoding="utf-8", newline=None) as source_file:
            for line_number, source_line in enumerate(source_file, start=1):
                if line_number in expected_lines:
                    actual_lines[line_number] = source_line.rstrip("\n")
    except (OSError, UnicodeDecodeError):
        return _invalid("PATCH_TARGET_UNREADABLE")

    for line_number, expected in expected_lines.items():
        if actual_lines.get(line_number) != expected:
            return _invalid("PATCH_CONTEXT_MISMATCH")
    return PatchValidationResult(True, patch_diff, ())


