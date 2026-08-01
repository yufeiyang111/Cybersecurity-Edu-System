"""确定性扫描执行阶段。

该模块执行已注册语言 Scanner、依赖解析和 OSV SCA，并把规范化结果持久化。
它不管理任务状态机、HTTP 请求或队列生命周期。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from app import db
from app.models.security import FindingEvidence, ScanTask, SecurityFinding, SnapshotDependency
from app.services.dependency_scanner import DependencyCoordinate, dependency_coordinate_hash, discover_dependencies
from app.services.osv_client import OSVVulnerabilityProvider
from app.services.scanners import get_scanners
from app.services.scanners.base import BaseLanguageScanner, RawFinding
from app.services.scanners.contracts import NormalizedFinding, ScannerDescriptor
from app.services.scanners.normalizer import finding_fingerprint, normalize_finding
from app.services.scanners.registry import descriptor_for


@dataclass(frozen=True)
class ScanExecutionResult:
    """一次扫描执行阶段的可序列化汇总，不携带任何原始代码内容。"""

    warnings: list[dict[str, str]]
    languages: list[str]
    completed_scanners: int
    dependencies_count: int
    sca_findings_count: int
    sca_enabled: bool
    findings_count: int


def execute_scan_stages(
    task: ScanTask,
    snapshot_root: Path,
    *,
    scanners: Sequence[BaseLanguageScanner] | None = None,
    vulnerability_provider: OSVVulnerabilityProvider | None = None,
) -> ScanExecutionResult:
    """运行 Scanner、依赖和 SCA 阶段，并返回持久化后的汇总。"""
    warnings: list[dict[str, str]] = []
    detected_languages: list[str] = []
    completed_scanners = 0

    active_scanners = list(scanners if scanners is not None else get_scanners())
    for scanner in active_scanners:
        if not scanner.can_handle(snapshot_root):
            continue
        descriptor = descriptor_for(scanner)
        try:
            scanner.detect_project(snapshot_root)
            for finding in _all_findings(scanner, snapshot_root):
                persist_finding(task, normalize_finding(finding, descriptor))
            detected_language = str(getattr(scanner, "language", descriptor.supported_languages[0]))
            if detected_language not in detected_languages:
                detected_languages.append(detected_language)
            completed_scanners += 1
        except Exception as exc:  # Scanner failure is isolated and source text is never exposed.
            warnings.append(
                {
                    "scanner": descriptor.name,
                    "error": type(exc).__name__,
                }
            )

    dependencies = persist_dependencies(task, discover_dependencies(snapshot_root))
    provider = vulnerability_provider or OSVVulnerabilityProvider()
    try:
        sca_result = provider.query_batch(dependencies)
    except Exception as exc:  # SCA failure must not erase completed deterministic findings.
        sca_findings_count = 0
        sca_enabled = False
        warnings.append({"scanner": "sca", "error": type(exc).__name__})
    else:
        sca_findings_count = persist_sca_findings(task, dict(sca_result.vulnerabilities))
        sca_enabled = "OSV_DISABLED" not in sca_result.warnings
        warnings.extend({"scanner": "sca", "error": warning} for warning in sca_result.warnings)

    return ScanExecutionResult(
        warnings=warnings,
        languages=sorted(detected_languages),
        completed_scanners=completed_scanners,
        dependencies_count=len(dependencies),
        sca_findings_count=sca_findings_count,
        sca_enabled=sca_enabled,
        findings_count=SecurityFinding.query.filter_by(task_id=task.id).count(),
    )


def persist_finding(
    task: ScanTask,
    finding: RawFinding | NormalizedFinding,
    *,
    descriptor: ScannerDescriptor | None = None,
) -> SecurityFinding:
    """持久化统一 Finding，并为旧 RawFinding 调用保留兼容入口。"""
    normalized = (
        finding
        if isinstance(finding, NormalizedFinding)
        else normalize_finding(finding, descriptor or _LEGACY_DESCRIPTOR)
    )
    persisted = SecurityFinding.query.filter_by(
        task_id=task.id,
        fingerprint=normalized.fingerprint,
    ).one_or_none()
    if persisted is None:
        persisted = SecurityFinding(
            task_id=task.id,
            fingerprint=normalized.fingerprint,
            rule_id=normalized.rule_id,
            category=normalized.category,
            severity=normalized.severity,
            cwe_id=normalized.cwe_id,
            cve_id=normalized.cve_id,
            file_path=normalized.file_path,
            start_line=normalized.start_line,
            end_line=normalized.end_line,
            message=normalized.message,
            confidence=normalized.confidence,
            rule_version=normalized.rule_version or "baseline-rules-v2",
        )
        db.session.add(persisted)
        db.session.flush()
    else:
        persisted.cve_id = normalized.cve_id or persisted.cve_id
        persisted.confidence = normalized.confidence
        persisted.rule_version = normalized.rule_version or persisted.rule_version or "baseline-rules-v2"

    evidence_type = _evidence_type(normalized)
    evidence_exists = FindingEvidence.query.filter_by(
        finding_id=persisted.id,
        evidence_type=evidence_type,
        source_uri=normalized.file_path,
        start_line=normalized.start_line,
        end_line=normalized.end_line,
    ).one_or_none()
    if evidence_exists is None:
        db.session.add(
            FindingEvidence(
                finding_id=persisted.id,
                evidence_type=evidence_type,
                content_redacted=normalized.evidence_preview,
                secret_hash=normalized.secret_sha256,
                source_uri=normalized.file_path,
                start_line=normalized.start_line,
                end_line=normalized.end_line,
                score=normalized.confidence,
            )
        )
    return persisted


def _evidence_type(finding: NormalizedFinding) -> str:
    if finding.secret_sha256 or finding.category == "secret":
        return "secret"
    if finding.category == "sca" or finding.source_type == "dependency":
        return "dependency"
    if finding.category == "configuration":
        return "configuration"
    return "code"


def persist_dependencies(
    task: ScanTask,
    dependencies: Iterable[DependencyCoordinate],
) -> list[DependencyCoordinate]:
    """把不可变快照的依赖库存按坐标哈希幂等持久化。"""
    persisted_coordinates: list[DependencyCoordinate] = []
    for dependency in dependencies:
        coordinate_hash = dependency_coordinate_hash(dependency)
        existing = SnapshotDependency.query.filter_by(
            snapshot_id=task.snapshot_id,
            coordinate_hash=coordinate_hash,
        ).one_or_none()
        if existing is None:
            db.session.add(
                SnapshotDependency(
                    snapshot_id=task.snapshot_id,
                    ecosystem=dependency.ecosystem,
                    package_name=dependency.package_name,
                    version=dependency.version,
                    manifest_path=dependency.manifest_path,
                    coordinate_hash=coordinate_hash,
                    is_direct=dependency.is_direct,
                    source_line=dependency.source_line,
                )
            )
        persisted_coordinates.append(dependency)
    db.session.flush()
    return persisted_coordinates


def persist_sca_findings(
    task: ScanTask,
    vulnerabilities: dict[DependencyCoordinate, tuple],
) -> int:
    """将 OSV advisory 转换为与 SAST 一致的持久化 Finding。"""
    persisted_count = 0
    for dependency, advisories in vulnerabilities.items():
        for advisory in advisories:
            aliases = ", ".join(advisory.aliases[:4])
            message = advisory.summary or f"依赖 {dependency.package_name}@{dependency.version} 存在安全公告"
            finding = RawFinding(
                rule_id=f"OSV-{advisory.id}",
                category="sca",
                severity=_sca_severity(advisory.severity),
                cwe_id=None,
                file_path=dependency.manifest_path,
                start_line=dependency.source_line or 1,
                end_line=dependency.source_line or 1,
                message=message[:1000],
                evidence_preview=(
                    f"{dependency.ecosystem}:{dependency.package_name}@{dependency.version}; "
                    f"advisory={advisory.id}; aliases={aliases}; "
                    f"fixed={', '.join(advisory.fixed_versions[:4]) or 'unknown'}"
                )[:1000],
                confidence=0.9,
                cve_id=next((alias for alias in advisory.aliases if alias.startswith("CVE-")), None),
                source_type="dependency",
                rule_version="osv-v1",
            )
            persist_finding(task, normalize_finding(finding, _SCA_DESCRIPTOR))
            persisted_count += 1
    return persisted_count


def _all_findings(scanner: BaseLanguageScanner, snapshot_root: Path) -> Iterable[RawFinding]:
    yield from scanner.run_sast(snapshot_root)
    yield from scanner.run_secret_scan(snapshot_root)


_LEGACY_DESCRIPTOR = ScannerDescriptor(
    name="legacy-scanner",
    version="1.0.0",
    supported_languages=("unknown",),
    categories=("sast",),
)
_SCA_DESCRIPTOR = ScannerDescriptor(
    name="osv-sca",
    version="1.0.0",
    supported_languages=("dependency",),
    categories=("sca",),
)


def _finding_fingerprint(finding: RawFinding) -> str:
    """为旧内部调用名称保留兼容入口，并转发到统一 Finding 指纹算法。"""
    normalized = normalize_finding(finding, _LEGACY_DESCRIPTOR)
    return finding_fingerprint(
        rule_id=normalized.rule_id,
        category=normalized.category,
        file_path=normalized.file_path,
        start_line=normalized.start_line,
        end_line=normalized.end_line,
        cve_id=normalized.cve_id,
        secret_sha256=normalized.secret_sha256,
    )


def _sca_severity(value: str) -> str:
    return value if value in {"critical", "high", "medium", "low", "info"} else "medium"
