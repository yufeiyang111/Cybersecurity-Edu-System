from __future__ import annotations

from datetime import datetime, timedelta

import requests

from app import db
from app.models.security import VulnerabilityAdvisoryCache
from app.services.dependency_scanner import DependencyCoordinate
from app.services.osv_client import OSVVulnerabilityProvider


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.closed = False

    def json(self):
        return self._payload

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.trust_env = None
        self.verify = None
        self.posts = []
        self.closed = False

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response

    def close(self):
        self.closed = True


def _provider(
    *,
    session: FakeSession | None = None,
    enabled: bool = True,
    max_dependencies: int = 2,
) -> OSVVulnerabilityProvider:
    return OSVVulnerabilityProvider(
        enabled=enabled,
        api_url="https://api.osv.dev/v1/querybatch",
        timeout_seconds=9,
        cache_ttl_seconds=3600,
        max_dependencies=max_dependencies,
        session=session,
    )


def test_disabled_provider_does_not_make_network_call():
    session = FakeSession(response=FakeResponse({"results": []}))
    dependency = DependencyCoordinate("PyPI", "requests", "2.31.0", "requirements.txt", True, 1)

    result = _provider(session=session, enabled=False).query_batch([dependency])

    assert result.warnings == ("OSV_DISABLED",)
    assert result.vulnerabilities == {dependency: ()}
    assert session.posts == []


def test_dependency_limit_skips_remote_queries_and_reports_a_safe_warning():
    dependencies = [
        DependencyCoordinate("PyPI", "requests", "2.31.0", "requirements.txt", True, 1),
        DependencyCoordinate("PyPI", "flask", "3.0.0", "requirements.txt", True, 2),
        DependencyCoordinate("PyPI", "werkzeug", "3.0.0", "requirements.txt", True, 3),
    ]
    session = FakeSession(error=AssertionError("OSV query must be bounded before a network call"))

    result = _provider(session=session, max_dependencies=2).query_batch(dependencies)

    assert result.warnings == ("OSV_DEPENDENCY_LIMIT_EXCEEDED",)
    assert result.vulnerabilities == {dependency: () for dependency in dependencies}
    assert session.posts == []

def test_provider_uses_minimal_payload_and_parses_safe_vulnerability_result():
    session = FakeSession(
        response=FakeResponse(
            {
                "results": [
                    {
                        "vulns": [
                            {
                                "id": "GHSA-abcd-1234-efgh",
                                "aliases": ["CVE-2024-1234", "GHSA-abcd-1234-efgh", "OTHER-1"],
                                "summary": "A test advisory",
                                "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
                                "affected": [{"ranges": [{"events": [{"introduced": "0"}, {"fixed": "2.32.0"}]}]}],
                                "database_specific": {"severity": "HIGH", "cwe_ids": ["CWE-79"]},
                            }
                        ]
                    }
                ]
            }
        )
    )
    dependency = DependencyCoordinate("PyPI", "requests", "2.31.0", "private/path/requirements.txt", True, 18)

    result = _provider(session=session).query_batch([dependency])

    assert result.warnings == ()
    vulnerability = result.vulnerabilities[dependency][0]
    assert vulnerability.id == "GHSA-abcd-1234-efgh"
    assert vulnerability.aliases == ("CVE-2024-1234", "GHSA-abcd-1234-efgh")
    assert vulnerability.severity == "critical"
    assert vulnerability.fixed_versions == ("2.32.0",)
    assert vulnerability.database_specific == {"severity": "HIGH", "cwe_ids": ["CWE-79"]}

    url, kwargs = session.posts[0]
    assert url == "https://api.osv.dev/v1/querybatch"
    assert kwargs["timeout"] == 9
    assert kwargs["json"] == {
        "queries": [{"package": {"ecosystem": "PyPI", "name": "requests"}, "version": "2.31.0"}]
    }
    assert "private/path" not in repr(kwargs["json"])
    assert "source_line" not in repr(kwargs["json"])
    assert session.trust_env is False
    assert session.verify is True


def test_provider_returns_cached_parsed_result_without_network(app):
    dependency = DependencyCoordinate("npm", "express", "4.18.3", "package.json", True, 4)
    provider = _provider(session=FakeSession(error=AssertionError("network must not be called")))
    cache = VulnerabilityAdvisoryCache(
        cache_key=provider.cache_key_for(dependency),
        ecosystem=dependency.ecosystem,
        package_name=dependency.package_name,
        version=dependency.version,
        response_json=[
            {
                "id": "CVE-2025-0001",
                "aliases": ["CVE-2025-0001"],
                "summary": "Cached response",
                "severity": "high",
                "fixed_versions": ["4.19.0"],
                "database_specific": {"severity": "HIGH"},
            }
        ],
        fetched_at=datetime.utcnow() - timedelta(minutes=1),
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.session.add(cache)
    db.session.commit()

    result = provider.query_batch([dependency])

    assert result.warnings == ()
    assert result.vulnerabilities[dependency][0].id == "CVE-2025-0001"
    assert provider.session.posts == []


def test_provider_failure_becomes_warning_without_crashing():
    dependency = DependencyCoordinate("Maven", "org.example:demo", "1.0.0", "pom.xml", True, 8)
    session = FakeSession(error=requests.RequestException("offline"))

    result = _provider(session=session).query_batch([dependency])

    assert result.warnings == ("OSV_REQUEST_FAILED",)
    assert result.vulnerabilities == {dependency: ()}
