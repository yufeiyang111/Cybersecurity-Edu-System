"""Contracts for deterministic, language-specific security scanners."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RawFinding:
    rule_id: str
    category: str
    severity: str
    cwe_id: str | None
    file_path: str
    start_line: int
    end_line: int
    message: str
    evidence_preview: str
    secret_sha256: str | None = None


@dataclass(frozen=True)
class ProjectProfile:
    language: str
    framework_hints: list[str]
    manifest_paths: list[str]


class BaseLanguageScanner(ABC):
    """Read-only scanner contract; implementations must never execute source code."""

    language: str

    @abstractmethod
    def can_handle(self, snapshot_root: Path) -> bool:
        """Return whether this scanner recognizes the extracted project."""

    @abstractmethod
    def detect_project(self, snapshot_root: Path) -> ProjectProfile:
        """Return project metadata derived from filenames and text only."""

    @abstractmethod
    def run_sast(self, snapshot_root: Path) -> list[RawFinding]:
        """Return deterministic static-analysis findings."""

    def run_secret_scan(self, snapshot_root: Path) -> list[RawFinding]:
        """Return secret findings. Default is no language-specific secret rules."""
        return []
