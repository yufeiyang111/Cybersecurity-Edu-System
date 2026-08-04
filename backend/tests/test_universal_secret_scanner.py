"""Universal Secret Scanner tests: independent baseline over every text file."""
from __future__ import annotations

from pathlib import Path

from app.services.scanners.universal.secret_scanner import UniversalSecretScanner


def _make_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir(parents=True, exist_ok=True)
    (root / "app.php").write_text("<?php\n$api_key = 'php-secret-value-12345';\n", encoding="utf-8")
    (root / "notes.md").write_text("config:\npassword = 'md-secret-value-12345'\n", encoding="utf-8")
    (root / "data.bin").write_bytes(b"\x89PNG\x00\x01\x02binary")
    return root


def test_universal_scan_finds_secrets_in_non_language_text(tmp_path):
    root = _make_project(tmp_path)
    findings = UniversalSecretScanner().run(root)
    by_path = {finding.file_path: finding for finding in findings}
    assert "app.php" in by_path, "PHP 文件没有语言扫描器也应有 Secret 覆盖"
    assert "notes.md" in by_path, "Markdown 文件也应有 Secret 覆盖"
    assert all(finding.category == "secret" for finding in findings)
    assert all(finding.severity == "high" for finding in findings)
    assert all(finding.secret_sha256 for finding in findings)
    assert "php-secret-value" not in " ".join(f.evidence_preview for f in findings), "证据必须脱敏"


def test_universal_scan_respects_exclusions(tmp_path):
    root = _make_project(tmp_path)

    class Matcher:
        def is_excluded(self, relative_path: str) -> bool:
            return relative_path == "notes.md"

    findings = UniversalSecretScanner(exclusion_matcher=Matcher()).run(root)
    assert all(finding.file_path != "notes.md" for finding in findings)
    assert any(finding.file_path == "app.php" for finding in findings)


def test_universal_scan_skips_binary_files(tmp_path):
    root = _make_project(tmp_path)
    findings = UniversalSecretScanner().run(root)
    assert all(finding.file_path != "data.bin" for finding in findings)
