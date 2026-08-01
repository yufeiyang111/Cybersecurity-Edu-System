"""Privacy-preserving OSV client for dependency vulnerability enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Iterable, Mapping

import requests
from flask import current_app, has_app_context
from sqlalchemy.exc import SQLAlchemyError

from app.config import (
    DEFAULT_SCA_CACHE_TTL_SECONDS,
    DEFAULT_SCA_MAX_DEPENDENCIES,
    DEFAULT_SCA_OSV_API_URL,
    DEFAULT_SCA_REQUEST_TIMEOUT_SECONDS,
)
from app.services.dependency_scanner import DependencyCoordinate


_SEVERITY_ORDER = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass(frozen=True)
class OSVVulnerability:
    id: str
    aliases: tuple[str, ...]
    summary: str
    severity: str
    fixed_versions: tuple[str, ...]
    database_specific: dict[str, Any]


@dataclass(frozen=True)
class OSVQueryResult:
    """Safe SCA result: parsed vulnerabilities plus stable warning codes only."""

    vulnerabilities: Mapping[DependencyCoordinate, tuple[OSVVulnerability, ...]]
    warnings: tuple[str, ...] = ()


class OSVVulnerabilityProvider:
    """Queries OSV using dependency coordinates only; no source path or code is transmitted."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        api_url: str | None = None,
        timeout_seconds: int | None = None,
        cache_ttl_seconds: int | None = None,
        max_dependencies: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        settings = current_app.config if has_app_context() else {}
        self.enabled = bool(settings.get("SCA_OSV_ENABLED", False) if enabled is None else enabled)
        self.api_url = str(settings.get("SCA_OSV_API_URL", DEFAULT_SCA_OSV_API_URL) if api_url is None else api_url)
        self.timeout_seconds = int(settings.get("SCA_REQUEST_TIMEOUT_SECONDS", DEFAULT_SCA_REQUEST_TIMEOUT_SECONDS) if timeout_seconds is None else timeout_seconds)
        self.cache_ttl_seconds = int(settings.get("SCA_CACHE_TTL_SECONDS", DEFAULT_SCA_CACHE_TTL_SECONDS) if cache_ttl_seconds is None else cache_ttl_seconds)
        self.max_dependencies = int(settings.get("SCA_MAX_DEPENDENCIES", DEFAULT_SCA_MAX_DEPENDENCIES) if max_dependencies is None else max_dependencies)
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.session.verify = True

    def cache_key_for(self, dependency: DependencyCoordinate) -> str:
        canonical = "\0".join((dependency.ecosystem, dependency.package_name, dependency.version))
        return sha256(canonical.encode("utf-8")).hexdigest()

    def query_batch(self, dependencies: Iterable[DependencyCoordinate]) -> OSVQueryResult:
        coordinates = _deduplicate_coordinates(dependencies)
        results: dict[DependencyCoordinate, tuple[OSVVulnerability, ...]] = {coordinate: () for coordinate in coordinates}
        if not coordinates:
            return OSVQueryResult(results)
        if not self.enabled:
            return OSVQueryResult(results, ("OSV_DISABLED",))
        if self.max_dependencies <= 0 or self.timeout_seconds <= 0 or self.cache_ttl_seconds <= 0:
            return OSVQueryResult(results, ("OSV_CONFIGURATION_INVALID",))
        if len(coordinates) > self.max_dependencies:
            return OSVQueryResult(results, ("OSV_DEPENDENCY_LIMIT_EXCEEDED",))

        cached, misses = self._read_cached(coordinates)
        results.update(cached)
        warnings: list[str] = []
        for batch in _batches(misses, self.max_dependencies):
            batch_results, batch_warning = self._query_remote(batch)
            results.update(batch_results)
            if batch_warning:
                warnings.append(batch_warning)
            elif batch_results:
                self._write_cache(batch_results)
        return OSVQueryResult(results, tuple(dict.fromkeys(warnings)))

    def _query_remote(
        self, coordinates: list[DependencyCoordinate]
    ) -> tuple[dict[DependencyCoordinate, tuple[OSVVulnerability, ...]], str | None]:
        payload = {
            "queries": [
                {"package": {"ecosystem": coordinate.ecosystem, "name": coordinate.package_name}, "version": coordinate.version}
                for coordinate in coordinates
            ]
        }
        try:
            response = self.session.post(
                self.api_url,
                json=payload,
                timeout=self.timeout_seconds,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
        except requests.RequestException:
            return {}, "OSV_REQUEST_FAILED"
        try:
            if response.status_code != 200:
                return {}, "OSV_HTTP_ERROR"
            payload = response.json()
        except (ValueError, TypeError):
            return {}, "OSV_RESPONSE_INVALID"
        finally:
            response.close()

        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            return {}, "OSV_RESPONSE_INVALID"
        response_items = payload["results"]
        if len(response_items) != len(coordinates):
            return {}, "OSV_RESPONSE_INVALID"

        parsed: dict[DependencyCoordinate, tuple[OSVVulnerability, ...]] = {}
        for coordinate, item in zip(coordinates, response_items, strict=True):
            if not isinstance(item, dict):
                return {}, "OSV_RESPONSE_INVALID"
            raw_vulnerabilities = item.get("vulns", [])
            if not isinstance(raw_vulnerabilities, list):
                return {}, "OSV_RESPONSE_INVALID"
            parsed[coordinate] = _parse_vulnerabilities(raw_vulnerabilities)
        return parsed, None

    def _read_cached(
        self, coordinates: list[DependencyCoordinate]
    ) -> tuple[dict[DependencyCoordinate, tuple[OSVVulnerability, ...]], list[DependencyCoordinate]]:
        if not has_app_context():
            return {}, coordinates
        try:
            from app import db
            from app.models.security import VulnerabilityAdvisoryCache

            now = datetime.utcnow()
            cached: dict[DependencyCoordinate, tuple[OSVVulnerability, ...]] = {}
            misses: list[DependencyCoordinate] = []
            for coordinate in coordinates:
                entry = VulnerabilityAdvisoryCache.query.filter_by(cache_key=self.cache_key_for(coordinate)).one_or_none()
                if entry is None or entry.expires_at is None or entry.expires_at <= now or not _cache_entry_matches(entry, coordinate):
                    misses.append(coordinate)
                    continue
                raw_vulnerabilities = entry.response_json if isinstance(entry.response_json, list) else []
                cached[coordinate] = _parse_vulnerabilities(raw_vulnerabilities)
            return cached, misses
        except SQLAlchemyError:
            db.session.rollback()
            return {}, coordinates

    def _write_cache(self, results: Mapping[DependencyCoordinate, tuple[OSVVulnerability, ...]]) -> None:
        if not results or not has_app_context():
            return
        try:
            from app import db
            from app.models.security import VulnerabilityAdvisoryCache

            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=self.cache_ttl_seconds)
            for coordinate, vulnerabilities in results.items():
                cache_key = self.cache_key_for(coordinate)
                entry = VulnerabilityAdvisoryCache.query.filter_by(cache_key=cache_key).one_or_none()
                if entry is None:
                    entry = VulnerabilityAdvisoryCache(
                        cache_key=cache_key,
                        ecosystem=coordinate.ecosystem,
                        package_name=coordinate.package_name,
                        version=coordinate.version,
                        response_json=[],
                        fetched_at=now,
                        expires_at=expires_at,
                    )
                    db.session.add(entry)
                entry.response_json = [_vulnerability_to_cache_record(vulnerability) for vulnerability in vulnerabilities]
                entry.fetched_at = now
                entry.expires_at = expires_at
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()


def _deduplicate_coordinates(dependencies: Iterable[DependencyCoordinate]) -> list[DependencyCoordinate]:
    unique = {
        (coordinate.ecosystem, coordinate.package_name, coordinate.version): coordinate
        for coordinate in dependencies
        if isinstance(coordinate, DependencyCoordinate)
    }
    return sorted(unique.values(), key=lambda item: (item.ecosystem.casefold(), item.package_name.casefold(), item.version, item.manifest_path, item.source_line or -1))


def _batches(items: list[DependencyCoordinate], size: int) -> Iterable[list[DependencyCoordinate]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _cache_entry_matches(entry: Any, coordinate: DependencyCoordinate) -> bool:
    return (
        entry.ecosystem == coordinate.ecosystem
        and entry.package_name == coordinate.package_name
        and entry.version == coordinate.version
    )


def _parse_vulnerabilities(raw_vulnerabilities: Any) -> tuple[OSVVulnerability, ...]:
    if not isinstance(raw_vulnerabilities, list):
        return ()
    parsed: list[OSVVulnerability] = []
    for raw in raw_vulnerabilities:
        vulnerability = _parse_vulnerability(raw)
        if vulnerability is not None:
            parsed.append(vulnerability)
    return tuple(sorted(parsed, key=lambda item: item.id))


def _parse_vulnerability(raw: Any) -> OSVVulnerability | None:
    if not isinstance(raw, dict):
        return None
    advisory_id = raw.get("id")
    if not isinstance(advisory_id, str) or not advisory_id.strip():
        return None
    aliases = tuple(dict.fromkeys(alias for alias in raw.get("aliases", []) if isinstance(alias, str) and _is_security_alias(alias)))
    summary = raw.get("summary") if isinstance(raw.get("summary"), str) else ""
    database_specific = _safe_json_value(raw.get("database_specific"))
    if not isinstance(database_specific, dict):
        database_specific = {}
    fixed_versions = _fixed_versions(raw.get("affected"))
    severity = _derive_severity(raw.get("severity"), database_specific)
    return OSVVulnerability(
        id=advisory_id.strip(),
        aliases=aliases,
        summary=summary[:1000],
        severity=severity,
        fixed_versions=fixed_versions,
        database_specific=database_specific,
    )


def _is_security_alias(alias: str) -> bool:
    value = alias.strip().upper()
    return value.startswith("CVE-") or value.startswith("GHSA-")


def _fixed_versions(affected: Any) -> tuple[str, ...]:
    versions: list[str] = []
    if not isinstance(affected, list):
        return ()
    for affected_item in affected:
        if not isinstance(affected_item, dict) or not isinstance(affected_item.get("ranges"), list):
            continue
        for version_range in affected_item["ranges"]:
            if not isinstance(version_range, dict) or not isinstance(version_range.get("events"), list):
                continue
            for event in version_range["events"]:
                fixed = event.get("fixed") if isinstance(event, dict) else None
                if isinstance(fixed, str) and fixed.strip():
                    versions.append(fixed.strip())
    return tuple(sorted(set(versions)))


def _derive_severity(raw_severity: Any, database_specific: Mapping[str, Any]) -> str:
    if isinstance(raw_severity, list):
        for item in raw_severity:
            if not isinstance(item, dict):
                continue
            score = item.get("score")
            derived = _cvss_severity(score)
            if derived != "unknown":
                return derived
    database_severity = database_specific.get("severity")
    if isinstance(database_severity, str):
        normalized = database_severity.strip().lower()
        if normalized in _SEVERITY_ORDER:
            return normalized
    return "unknown"


def _cvss_severity(score: Any) -> str:
    if not isinstance(score, str):
        return "unknown"
    try:
        numeric = float(score)
    except ValueError:
        numeric = None
    if numeric is not None:
        if numeric >= 9:
            return "critical"
        if numeric >= 7:
            return "high"
        if numeric >= 4:
            return "medium"
        if numeric > 0:
            return "low"
        return "unknown"
    vector = score.upper()
    if "CVSS:" not in vector:
        return "unknown"
    impacts = re_findall(r"/[CIA]:([NLH])", vector)
    if impacts.count("H") >= 2:
        return "critical"
    if "H" in impacts:
        return "high"
    if "L" in impacts:
        return "medium"
    return "low" if impacts else "unknown"


def re_findall(pattern: str, value: str) -> list[str]:
    import re

    return re.findall(pattern, value)


def _safe_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:1000]
    if isinstance(value, list):
        return [_safe_json_value(item) for item in value[:100]]
    if isinstance(value, dict):
        return {str(key)[:100]: _safe_json_value(item) for key, item in list(value.items())[:100]}
    return None


def _vulnerability_to_cache_record(vulnerability: OSVVulnerability) -> dict[str, Any]:
    return {
        "id": vulnerability.id,
        "aliases": list(vulnerability.aliases),
        "summary": vulnerability.summary,
        "severity": vulnerability.severity,
        "fixed_versions": list(vulnerability.fixed_versions),
        "database_specific": vulnerability.database_specific,
    }
