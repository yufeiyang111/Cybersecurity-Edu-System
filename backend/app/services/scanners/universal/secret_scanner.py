"""Universal Secret Scanner: runs exactly once per task over every text file.

This scanner is independent of the language scanners so that projects with no
language coverage (PHP/YAML/Markdown-only) still receive the secret baseline.
It shares the hardened secret regex and masking from the scanner base module.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from app.services.scan_coverage.classifier import detect_text
from app.services.scanners.base import RawFinding, SECRET_ASSIGNMENT, _mask_secret


class UniversalSecretScanner:
    """Deterministic line-level secret scan over all extracted text files."""

    language = "universal"
    scanner_name = "universal_secret"
    scanner_version = "1.0.0"

    def __init__(self, exclusion_matcher=None) -> None:
        self._exclusion_matcher = exclusion_matcher

    def configure_exclusions(self, matcher) -> None:
        self._exclusion_matcher = matcher

    def run(self, snapshot_root: Path) -> list[RawFinding]:
        findings: list[RawFinding] = []
        for path in _text_files(snapshot_root):
            if self._is_excluded(path, snapshot_root):
                continue
            text = _read_text(path)
            if text is None:
                continue
            relative_path = path.relative_to(snapshot_root).as_posix()
            for line_number, line in enumerate(text.splitlines(), start=1):
                match = SECRET_ASSIGNMENT.search(line)
                if match is None:
                    continue
                secret = match.group("value")
                findings.append(
                    RawFinding(
                        rule_id="GENERIC-HARDCODED-SECRET",
                        category="secret",
                        severity="high",
                        cwe_id="CWE-798",
                        file_path=relative_path,
                        start_line=line_number,
                        end_line=line_number,
                        message="检测到疑似硬编码敏感信息，请移至受控密钥管理或环境变量。",
                        evidence_preview=_mask_secret(secret),
                        secret_sha256=sha256(secret.encode("utf-8")).hexdigest(),
                    )
                )
        return findings

    def _is_excluded(self, path: Path, snapshot_root: Path) -> bool:
        if self._exclusion_matcher is None:
            return False
        relative_path = path.relative_to(snapshot_root).as_posix()
        return self._exclusion_matcher.is_excluded(relative_path)


def _text_files(snapshot_root: Path) -> list[Path]:
    return sorted(
        path
        for path in snapshot_root.rglob("*")
        if path.is_file() and detect_text(path)
    )


def _read_text(path: Path) -> str | None:
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except (OSError, UnicodeDecodeError):
            continue
    return None
