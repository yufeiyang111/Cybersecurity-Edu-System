from __future__ import annotations

from sqlalchemy import text
from app import db


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
