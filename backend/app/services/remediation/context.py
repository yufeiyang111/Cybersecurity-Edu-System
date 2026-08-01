"""Bounded, redacted local context extraction for remediation."""
from __future__ import annotations

from app.models.security import SecurityFinding
from app.services.security_knowledge import _redact_text

from .snapshot_paths import _normalize_relative_path, _safe_target, _snapshot_root
from .types import _CodeContext

def _value(value: object) -> str:
    return str(getattr(value, "value", value))

def _extract_code_context(
    storage_path: str | None,
    finding: SecurityFinding,
    max_chars: int,
) -> _CodeContext:
    file_path = _normalize_relative_path(finding.file_path, allow_diff_prefix=False)
    if file_path is None:
        return _CodeContext("", 0, (), "", ("CONTEXT_PATH_INVALID",))
    if _value(finding.category) == "secret":
        return _CodeContext(file_path, 0, (), "", ("SECRET_CONTEXT_WITHHELD",))

    root = _snapshot_root(storage_path or "")
    target = _safe_target(root, file_path) if root is not None else None
    if target is None:
        return _CodeContext(file_path, 0, (), "", ("CONTEXT_UNAVAILABLE",))

    start_line = max(1, int(finding.start_line or 1) - 2)
    end_line = max(start_line, int(finding.end_line or finding.start_line or 1) + 2)
    raw_lines: list[str] = []
    try:
        with target.open("r", encoding="utf-8", newline=None) as source_file:
            for line_number, line in enumerate(source_file, start=1):
                if line_number < start_line:
                    continue
                if line_number > end_line:
                    break
                raw_lines.append(line.rstrip("\n"))
    except (OSError, UnicodeDecodeError):
        return _CodeContext(file_path, 0, (), "", ("CONTEXT_UNAVAILABLE",))

    if not raw_lines:
        return _CodeContext(file_path, 0, (), "", ("CONTEXT_UNAVAILABLE",))
    rendered_lines: list[str] = []
    warning_codes: list[str] = []
    for offset, raw_line in enumerate(raw_lines):
        rendered_line = f"{start_line + offset}: {_redact_text(raw_line)}"
        candidate = "\n".join([*rendered_lines, rendered_line])
        if len(candidate) > max_chars:
            warning_codes.append("CONTEXT_TRUNCATED")
            break
        rendered_lines.append(rendered_line)
    if not rendered_lines:
        return _CodeContext(file_path, start_line, tuple(raw_lines), "", ("CONTEXT_TRUNCATED",))
    return _CodeContext(
        file_path=file_path,
        first_line=start_line,
        raw_lines=tuple(raw_lines),
        rendered="\n".join(rendered_lines),
        warning_codes=tuple(warning_codes),
    )


