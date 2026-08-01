"""Value objects used by the trusted remediation domain."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.security import RemediationSuggestion


@dataclass(frozen=True)
class PatchValidationResult:
    """Result of a non-mutating patch safety and context validation."""

    is_valid: bool
    patch_diff: str | None
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class RemediationGenerationResult:
    """Internal result shape retained for provider/fallback parity."""

    suggestion: RemediationSuggestion | None
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class _ProviderCallResult:
    payload: dict[str, Any] | None
    warning_code: str | None = None


@dataclass(frozen=True)
class _PatchHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: tuple[str, ...]


@dataclass(frozen=True)
class _CodeContext:
    file_path: str
    first_line: int
    raw_lines: tuple[str, ...]
    rendered: str
    warning_codes: tuple[str, ...]


