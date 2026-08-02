from __future__ import annotations

import pytest
from sqlalchemy import text

from app import db
from app.services.runtime_health import (
    _ping_qdrant,
    _vector_component,
    readiness_payload,
)


def test_liveness_and_request_correlation_id_are_safe(app):
    client = app.test_client()

    response = client.get("/api/health/live", headers={"X-Request-ID": "phase4-test-1"})

    assert response.status_code == 200
    assert response.json == {"status": "healthy", "service": "CyberGuard API"}
    assert response.headers["X-Request-ID"] == "phase4-test-1"


def test_invalid_request_correlation_id_is_replaced(app):
    response = app.test_client().get("/api/health", headers={"X-Request-ID": "../secret"})

    request_id = response.headers.get("X-Request-ID", "")
    assert response.status_code == 200
    assert request_id
    assert request_id != "../secret"
    assert len(request_id) <= 64


def test_readiness_reports_required_and_optional_components_without_secrets(app):
    with app.app_context():
        db.session.execute(text("SELECT 1"))

    response = app.test_client().get("/api/health/ready")

    assert response.status_code == 200
    payload = response.json
    assert payload["status"] == "ready"
    assert payload["components"]["database"]["status"] == "healthy"
    assert payload["components"]["workspace_storage"]["status"] == "healthy"
    assert "password" not in repr(payload).lower()
    assert "secret" not in repr(payload).lower()


def test_vector_component_disabled_when_vector_not_enabled():
    component = _vector_component({"SECURITY_KNOWLEDGE_VECTOR_ENABLED": False})

    assert component.status == "disabled"
    assert component.required is False


def test_vector_component_reports_unavailable_on_ping_failure(monkeypatch):
    def _broken_ping(backend, config):
        raise RuntimeError("connection refused")

    monkeypatch.setattr("app.services.runtime_health._ping_vector_backend", _broken_ping)

    component = _vector_component({"SECURITY_KNOWLEDGE_VECTOR_ENABLED": True})

    assert component.status == "unavailable"
    assert component.required is False


def test_vector_component_reports_healthy_when_ping_succeeds(monkeypatch):
    monkeypatch.setattr(
        "app.services.runtime_health._ping_vector_backend",
        lambda backend, config: True,
    )

    component = _vector_component({"SECURITY_KNOWLEDGE_VECTOR_ENABLED": True})

    assert component.status == "healthy"
    assert component.required is False


def test_ping_qdrant_fails_fast_on_unreachable_endpoint(monkeypatch):
    def _refused(*args, **kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", _refused)

    assert _ping_qdrant({"QDRANT_URL": "http://127.0.0.1:1"}) is False


def test_ping_qdrant_sets_loopback_no_proxy(monkeypatch):
    captured = {}

    def _fake_urlopen(url, timeout):
        captured["url"] = url
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    assert _ping_qdrant({"QDRANT_URL": "http://127.0.0.1:6333"}) is True
    assert captured["url"] == "http://127.0.0.1:6333/healthz"
    assert captured["timeout"] == 2.0


class _FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


@pytest.mark.parametrize(
    ("config", "expected_status"),
    [
        ({"SECURITY_KNOWLEDGE_VECTOR_ENABLED": False}, "disabled"),
        (
            {
                "SECURITY_KNOWLEDGE_VECTOR_ENABLED": True,
                "VECTOR_BACKEND": "bogus",
                "QDRANT_URL": "http://127.0.0.1:1",
            },
            "unavailable",
        ),
    ],
)
def test_vector_component_handles_configuration_edge_cases(config, expected_status, monkeypatch):
    monkeypatch.setattr(
        "app.services.runtime_health._ping_vector_backend",
        lambda backend, config: False,
    )
    component = _vector_component(config)
    assert component.status == expected_status
    assert "127.0.0.1" not in repr(component.to_dict())
