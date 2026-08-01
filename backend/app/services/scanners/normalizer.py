"""RawFinding 到统一 Finding 的安全规范化边界。"""
from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from .base import RawFinding
from .contracts import NormalizedFinding, ScannerDescriptor


def normalize_finding(raw: RawFinding, descriptor: ScannerDescriptor) -> NormalizedFinding:
    """规范化字段、限制证据长度并生成跨 Scanner 稳定指纹。"""
    confidence = _confidence(raw.confidence)
    category = _safe_text(raw.category, "sast", 64)
    source_type = _safe_text(raw.source_type or category, category, 64)
    file_path = _safe_text(raw.file_path, "[unknown]", 1024)
    message = _safe_text(raw.message, "安全规则命中", 4000)
    evidence = _safe_text(raw.evidence_preview, "", 1000)
    cwe_id = _optional_text(raw.cwe_id, 64)
    cve_id = _optional_text(raw.cve_id, 64)
    rule_version = _optional_text(raw.rule_version, 100)
    metadata = _safe_metadata(raw.metadata)
    fingerprint = finding_fingerprint(
        rule_id=_safe_text(raw.rule_id, "UNKNOWN-RULE", 128),
        category=category,
        file_path=file_path,
        start_line=max(1, int(raw.start_line)),
        end_line=max(1, int(raw.end_line)),
        cve_id=cve_id,
        secret_sha256=raw.secret_sha256,
    )
    return NormalizedFinding(
        scanner_name=descriptor.name,
        scanner_version=descriptor.version,
        rule_id=_safe_text(raw.rule_id, "UNKNOWN-RULE", 128),
        category=category,
        severity=_safe_text(raw.severity, "medium", 32),
        confidence=confidence,
        cwe_id=cwe_id,
        cve_id=cve_id,
        file_path=file_path,
        start_line=max(1, int(raw.start_line)),
        end_line=max(1, int(raw.end_line)),
        message=message,
        evidence_preview=evidence,
        source_type=source_type,
        fingerprint=fingerprint,
        secret_sha256=_optional_text(raw.secret_sha256, 128),
        rule_version=rule_version,
        metadata=metadata,
    )


def finding_fingerprint(
    *,
    rule_id: str,
    category: str,
    file_path: str,
    start_line: int,
    end_line: int,
    cve_id: str | None = None,
    secret_sha256: str | None = None,
) -> str:
    """基于安全身份字段生成稳定指纹，不依赖可变证据文本或 Scanner 名称。"""
    canonical = json.dumps(
        {
            "rule_id": rule_id,
            "category": category,
            "file_path": file_path,
            "start_line": start_line,
            "end_line": end_line,
            "cve_id": cve_id,
            "secret_sha256": secret_sha256,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _confidence(value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 1.0
    return min(1.0, max(0.0, numeric))


def _safe_text(value: object, default: str, maximum: int) -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip()
    return normalized[:maximum] if normalized else default


def _optional_text(value: object, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized[:maximum] if normalized else None


def _safe_metadata(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, item in list(value.items())[:20]:
        if not isinstance(key, str) or not key.strip():
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            safe[key.strip()[:100]] = item if not isinstance(item, str) else item[:500]
    return safe
