"""Scanner Plugin 与规范化 Finding 的领域契约。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScannerDescriptor:
    """描述一个 Scanner 的稳定身份、版本和能力范围。"""

    name: str
    version: str
    supported_languages: tuple[str, ...]
    categories: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("scanner name must not be empty")
        if not self.version.strip():
            raise ValueError("scanner version must not be empty")
        if not self.supported_languages:
            raise ValueError("scanner must declare at least one language")


@dataclass(frozen=True)
class NormalizedFinding:
    """跨 Scanner 的安全 Finding 领域表示，不携带未脱敏源码。"""

    scanner_name: str
    scanner_version: str
    rule_id: str
    category: str
    severity: str
    confidence: float
    cwe_id: str | None
    cve_id: str | None
    file_path: str
    start_line: int
    end_line: int
    message: str
    evidence_preview: str
    source_type: str
    fingerprint: str
    secret_sha256: str | None = None
    rule_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
