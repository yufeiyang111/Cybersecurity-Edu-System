from __future__ import annotations

from pathlib import Path

import pytest

from app.services.scanners.base import BaseLanguageScanner, ProjectProfile, RawFinding
from app.services.scanners.contracts import NormalizedFinding, ScannerDescriptor
from app.services.scanners.normalizer import normalize_finding
from app.services.scanners.registry import ScannerRegistry


class _GoScanner(BaseLanguageScanner):
    scanner_name = "go-baseline"
    scanner_version = "1.0.0"
    supported_languages = ("go",)
    categories = ("sast", "secret")
    language = "go"

    def can_handle(self, snapshot_root: Path) -> bool:
        return True

    def detect_project(self, snapshot_root: Path) -> ProjectProfile:
        return ProjectProfile("go", [], [])

    def run_sast(self, snapshot_root: Path) -> list[RawFinding]:
        return []


def test_registry_registers_new_language_without_orchestrator_changes():
    registry = ScannerRegistry()
    registry.register(_GoScanner)

    scanners = registry.create_scanners()
    descriptors = registry.describe()

    assert len(scanners) == 1
    assert scanners[0].scanner_name == "go-baseline"
    assert descriptors == [
        ScannerDescriptor(
            name="go-baseline",
            version="1.0.0",
            supported_languages=("go",),
            categories=("sast", "secret"),
        )
    ]


def test_registry_rejects_duplicate_scanner_names():
    registry = ScannerRegistry()
    registry.register(_GoScanner)

    with pytest.raises(ValueError, match="duplicate scanner"):
        registry.register(_GoScanner)


def test_normalizer_adds_scanner_metadata_and_stable_fingerprint():
    raw = RawFinding(
        rule_id="GO-CMD-EXEC",
        category="sast",
        severity="high",
        cwe_id="CWE-78",
        file_path="cmd/main.go",
        start_line=8,
        end_line=8,
        message="command execution",
        evidence_preview="exec.Command(userInput)",
    )
    descriptor = ScannerDescriptor(
        name="go-baseline",
        version="1.0.0",
        supported_languages=("go",),
        categories=("sast",),
    )

    normalized = normalize_finding(raw, descriptor)

    assert isinstance(normalized, NormalizedFinding)
    assert normalized.scanner_name == "go-baseline"
    assert normalized.scanner_version == "1.0.0"
    assert normalized.source_type == "sast"
    assert normalized.confidence == 1.0
    assert normalized.fingerprint
    assert normalized.fingerprint == normalize_finding(raw, descriptor).fingerprint


def test_registry_keeps_deterministic_order_and_capability_discovery():
    class _PythonScanner(_GoScanner):
        scanner_name = "python-baseline"
        scanner_version = "2.0.0"
        supported_languages = ("python",)

    registry = ScannerRegistry()
    registry.register(_GoScanner)
    registry.register(_PythonScanner)

    assert [item.name for item in registry.describe()] == ["go-baseline", "python-baseline"]
    assert registry.supports_language("python") is True
    assert registry.supports_language("rust") is False


def test_normalizer_deduplicates_same_finding_across_scanners():
    raw = RawFinding(
        rule_id="CWE-78-COMMAND-EXEC",
        category="sast",
        severity="high",
        cwe_id="CWE-78",
        file_path="src/main.go",
        start_line=12,
        end_line=12,
        message="command execution",
        evidence_preview="exec.Command(input)",
    )
    first = normalize_finding(
        raw,
        ScannerDescriptor("go-baseline", "1.0.0", ("go",), ("sast",)),
    )
    second = normalize_finding(
        raw,
        ScannerDescriptor("generic-sast", "2.0.0", ("go",), ("sast",)),
    )

    assert first.fingerprint == second.fingerprint
