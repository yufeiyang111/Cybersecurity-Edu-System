"""Restricted code evidence reading: the single source-read gate for A4.

Both agent tools and the HTTP API must go through this module so path-escape,
symlink, size and line-range rules are enforced in exactly one place.
"""
from __future__ import annotations

from pathlib import Path

from app.models.security import ProjectSnapshot
from app.services.project_security_graph.contracts import (
    CODE_SLICE_MAX_LINES,
    CODE_SLICE_MAX_REASON_CHARS,
)


class CodeSliceError(ValueError):
    """Raised for invalid slice requests (maps to HTTP 400)."""


class CodeSliceForbidden(PermissionError):
    """Raised when the request targets content outside the snapshot (maps to 403)."""


def validate_slice_params(start_line: int | None, end_line: int | None, reason: str | None) -> None:
    if not reason or not reason.strip():
        raise CodeSliceError("reason（读取理由）必填")
    if len(reason) > CODE_SLICE_MAX_REASON_CHARS:
        raise CodeSliceError(f"reason 不能超过 {CODE_SLICE_MAX_REASON_CHARS} 个字符")
    if start_line is None or end_line is None:
        raise CodeSliceError("start_line 与 end_line 必填")
    if start_line < 1 or end_line < start_line:
        raise CodeSliceError("start_line 必须大于 0 且不大于 end_line")
    if end_line - start_line + 1 > CODE_SLICE_MAX_LINES:
        raise CodeSliceError(f"切片行数不能超过 {CODE_SLICE_MAX_LINES} 行")


def resolve_slice_path(snapshot: ProjectSnapshot, file_path: str) -> Path:
    """Resolve a snapshot-relative file path, rejecting escapes and symlinks out of root."""
    if not snapshot.storage_path:
        raise CodeSliceForbidden("快照存储路径缺失")
    root = Path(snapshot.storage_path).resolve()
    if not root.is_dir():
        raise CodeSliceForbidden("快照存储目录不存在或不可读")
    candidate = (root / file_path).resolve()
    try:
        inside = candidate.is_relative_to(root)
    except AttributeError:  # Python < 3.9 fallback
        inside = str(candidate).startswith(str(root) + "\\") or str(candidate).startswith(
            str(root) + "/"
        )
    if not inside:
        raise CodeSliceForbidden("文件路径超出快照范围")
    if candidate.is_symlink():
        raise CodeSliceForbidden("不允许读取符号链接文件")
    if not candidate.is_file():
        raise CodeSliceError("文件不存在")
    return candidate


def read_code_slice(
    snapshot: ProjectSnapshot,
    file_path: str,
    start_line: int,
    end_line: int,
    reason: str,
) -> dict:
    """Return a restricted source slice as dict {file_path, start_line, end_line, lines}."""
    validate_slice_params(start_line, end_line, reason)
    target = resolve_slice_path(snapshot, file_path)
    try:
        source = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise CodeSliceError("文件读取失败") from exc
    all_lines = source.splitlines()
    if end_line > len(all_lines):
        raise CodeSliceError(f"end_line 超出文件行数（共 {len(all_lines)} 行）")
    return {
        "file_path": file_path,
        "start_line": start_line,
        "end_line": end_line,
        "lines": all_lines[start_line - 1 : end_line],
    }
