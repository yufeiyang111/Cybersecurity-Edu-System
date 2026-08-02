"""OAuth 第三方登录与绑定流程测试（mock 外部授权，不发起真实网络请求）。"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class OAuthTestConfig:
    APP_ENV = "testing"
    DEBUG = False
    TESTING = True
    SECRET_KEY = "a" * 32
    JWT_SECRET_KEY = "b" * 32
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
    SECURITY_WORKSPACE_ROOT = "security-workspaces"
    UPLOAD_FOLDER = "uploads"
    LOG_FILE = "logs/test.log"
    OAUTH_BACKEND_BASE_URL = "http://localhost:5001"
    OAUTH_FRONTEND_URL = "http://localhost:5173"
    GOOGLE_CLIENT_ID = "test-google-id"
    GOOGLE_CLIENT_SECRET = "test-google-secret"
    GITHUB_CLIENT_ID = "test-github-id"
    GITHUB_CLIENT_SECRET = "test-github-secret"
    REDIS_URL = "redis://localhost:6379/0"
    RQ_QUEUE_NAME = "cyberguard-security-test"
    RQ_ASYNC = False


class _FakeOAuthResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture()
def app():
    from app import create_app, db
    import app.models

    application = create_app(OAuthTestConfig)
    with application.app_context():
        db.create_all()
        _seed_default_role()
        yield application
        db.session.remove()
        db.drop_all()


def _seed_default_role():
    from app import db
    from app.models.user import Role

    if Role.query.filter_by(name="user").first() is None:
        db.session.add(Role(name="user", description="普通用户"))
        db.session.commit()


def _mock_github(monkeypatch, payload=None):
    from app.routes.oauth import oauth

    github = oauth.github
    monkeypatch.setattr(github, "authorize_access_token", lambda: {"access_token": "t"})
    data = payload or {
        "id": "1001",
        "login": "octo",
        "email": "octo@example.com",
        "avatar_url": "https://example.com/a.png",
        "name": "Octo",
    }
    monkeypatch.setattr(github, "get", lambda url: _FakeOAuthResponse(data))
    return data


def _mock_google(monkeypatch, payload=None):
    from app.routes.oauth import oauth

    google = oauth.google
    monkeypatch.setattr(google, "authorize_access_token", lambda: {"access_token": "t"})
    data = payload or {
        "sub": "2002",
        "email": "gmail@example.com",
        "name": "Gopher",
        "picture": "https://example.com/g.png",
    }
    monkeypatch.setattr(google, "get", lambda url: _FakeOAuthResponse(data))
    return data


def _create_user(username, email=None, **kwargs):
    from app import db
    from app.models.user import User

    user = User(username=username, email=email, role_id=_default_role_id(), **kwargs)
    db.session.add(user)
    db.session.commit()
    return user


def _default_role_id():
    from app.models.user import Role

    return Role.query.filter_by(name="user").first().id


def test_oauth_login_creates_new_user(app, monkeypatch):
    data = _mock_github(monkeypatch)
    client = app.test_client()

    resp = client.get("/api/auth/oauth/github/callback")

    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert location.startswith("http://localhost:5173/oauth/callback?token=")

    from app.models.user import User

    user = User.query.filter_by(oauth_provider="github", oauth_subject=str(data["id"])).first()
    assert user is not None
    assert user.email == data["email"]
    assert user.password_hash is None


def test_oauth_login_reuses_bound_user(app, monkeypatch):
    _mock_github(monkeypatch)
    bound = _create_user("octo", email="octo@example.com", oauth_provider="github", oauth_subject="1001")
    client = app.test_client()

    resp = client.get("/api/auth/oauth/github/callback")

    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert location.startswith("http://localhost:5173/oauth/callback?token=")

    from app.models.user import User

    assert User.query.count() == 1
    assert User.query.first().id == bound.id


def test_oauth_login_rejects_taken_email(app, monkeypatch):
    _mock_github(monkeypatch)
    _create_user("someone", email="octo@example.com")
    client = app.test_client()

    resp = client.get("/api/auth/oauth/github/callback")

    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert location.startswith("http://localhost:5173/oauth/callback?error=")
    assert "%E9%82%AE%E7%AE%B1%E5%B7%B2%E8%A2%AB%E6%B3%A8%E5%86%8C" in location


def _access_token_header(user):
    from flask_jwt_extended import create_access_token

    return {"Authorization": f"Bearer {create_access_token(identity=str(user.id))}"}


def test_oauth_bind_endpoint_returns_real_authorization_url(app):
    from unittest.mock import patch
    from app.routes.oauth import oauth

    user = _create_user("admin")
    client = app.test_client()

    with patch.object(
        oauth.github,
        "create_authorization_url",
        return_value={
            "url": "https://github.com/login/oauth/authorize?response_type=code&state=s1",
            "state": "s1",
        },
    ):
        resp = client.post("/api/auth/oauth/github/bind", headers=_access_token_header(user))

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["url"].startswith("https://github.com/login/oauth/authorize")
    assert "state=s1" in body["url"]


def test_oauth_bind_forces_account_picker(app):
    """Google/GitHub 绑定必须携带 prompt 参数，禁止静默跳过授权页。"""
    from unittest.mock import patch
    from app.routes.oauth import oauth

    user = _create_user("admin")
    client = app.test_client()

    cases = [
        ("google", "select_account consent"),
        ("github", "select_account"),
    ]
    for provider, expected_prompt in cases:
        with patch.object(
            getattr(oauth, provider),
            "create_authorization_url",
            return_value={"url": f"https://{provider}.com/auth?prompt={expected_prompt}", "state": "s1"},
        ) as mocked:
            resp = client.post(f"/api/auth/oauth/{provider}/bind", headers=_access_token_header(user))

        assert resp.status_code == 200, provider
        body = resp.get_json()
        assert "prompt=" in body["url"], provider
        assert "prompt=select_account" in body["url"], provider
        if provider == "google":
            assert "prompt=select_account consent" in body["url"], provider

        _, kwargs = mocked.call_args
        assert kwargs.get("prompt") == expected_prompt, provider


def test_oauth_authorize_forces_account_picker(app):
    """登录入口也必须携带 prompt=select_account，避免静默直接登录。"""
    from unittest.mock import patch
    from app.routes.oauth import oauth

    client = app.test_client()

    for provider in ("google", "github"):
        with patch.object(
            getattr(oauth, provider),
            "authorize_redirect",
            return_value=app.make_response(("", 302, {"Location": "https://provider.example/auth"})),
        ) as mocked:
            resp = client.get(f"/api/auth/oauth/{provider}/authorize")

        assert resp.status_code == 302, provider
        _, kwargs = mocked.call_args
        assert kwargs.get("prompt") == "select_account", provider


def test_oauth_bind_links_third_party_to_current_user(app, monkeypatch):
    _mock_github(monkeypatch)
    user = _create_user("admin")
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["oauth_bind_user_id"] = str(user.id)

    resp = client.get("/api/auth/oauth/github/callback")

    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("http://localhost:5173/user/profile?oauth_bind=ok")

    from app.models.user import User

    assert User.query.get(user.id).oauth_provider == "github"
    assert User.query.get(user.id).oauth_subject == "1001"


def test_oauth_bind_rejects_third_party_bound_elsewhere(app, monkeypatch):
    _mock_github(monkeypatch)
    _create_user("owner", email="owner@example.com", oauth_provider="github", oauth_subject="1001")
    other = _create_user("other")
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["oauth_bind_user_id"] = str(other.id)

    resp = client.get("/api/auth/oauth/github/callback")

    assert resp.status_code == 302
    assert "error=" in resp.headers["Location"]

    from app.models.user import User

    assert User.query.get(other.id).oauth_provider is None


def test_oauth_login_google_creates_new_user(app, monkeypatch):
    data = _mock_google(monkeypatch)
    client = app.test_client()

    resp = client.get("/api/auth/oauth/google/callback")

    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("http://localhost:5173/oauth/callback?token=")

    from app.models.user import User

    user = User.query.filter_by(oauth_provider="google", oauth_subject=str(data["sub"])).first()
    assert user is not None


def test_oauth_login_google_reuses_userinfo_from_id_token(app, monkeypatch):
    from app.routes.oauth import oauth

    google = oauth.google
    userinfo = {
        "sub": "3003",
        "email": "idtoken@example.com",
        "name": "IdToken User",
        "picture": "https://example.com/id.png",
    }
    token = {"access_token": "t", "userinfo": userinfo}

    def _fake_authorize_access_token():
        google.token = token
        return token

    monkeypatch.setattr(google, "authorize_access_token", _fake_authorize_access_token)

    def _should_not_be_called(url):
        raise AssertionError("userinfo 已从 id_token 解析，不应再发起网络请求")

    monkeypatch.setattr(google, "get", _should_not_be_called)
    client = app.test_client()

    resp = client.get("/api/auth/oauth/google/callback")

    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("http://localhost:5173/oauth/callback?token=")

    from app.models.user import User

    user = User.query.filter_by(oauth_provider="google", oauth_subject="3003").first()
    assert user is not None
    assert user.email == "idtoken@example.com"
    assert user.nickname == "IdToken User"


def test_oauth_bind_keeps_multiple_providers(app, monkeypatch):
    """同一账号可同时绑定 GitHub 与 Google，且均能用于登录。"""
    _mock_github(monkeypatch)
    _mock_google(monkeypatch)
    user = _create_user("admin")
    client = app.test_client()

    def _bind(provider):
        with client.session_transaction() as sess:
            sess["oauth_bind_user_id"] = str(user.id)
        resp = client.get(f"/api/auth/oauth/{provider}/callback")
        assert resp.status_code == 302
        assert resp.headers["Location"].startswith("http://localhost:5173/user/profile?oauth_bind=ok")

    _bind("github")
    _bind("google")

    from app.models.user import User

    refreshed = User.query.get(user.id)
    assert refreshed.oauth_provider == "google"
    assert refreshed.oauth_subject == "2002"
    assert refreshed.has_oauth_binding("github", "1001")
    assert refreshed.has_oauth_binding("google", "2002")
    assert len(refreshed.get_oauth_bindings()) == 2

    assert {b["provider"] for b in refreshed.to_dict()["oauth_bindings"]} == {"github", "google"}


def test_oauth_login_matches_binding_in_oauth_bindings_column(app, monkeypatch):
    """登录匹配不只查主绑定列，oauth_bindings 数组中的绑定同样可登录。"""
    _mock_github(monkeypatch)
    user = _create_user(
        "dual",
        email="dual@example.com",
        oauth_provider="google",
        oauth_subject="2002",
        oauth_bindings='[{"provider": "google", "subject": "2002"}, {"provider": "github", "subject": "1001"}]',
    )
    client = app.test_client()

    resp = client.get("/api/auth/oauth/github/callback")

    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("http://localhost:5173/oauth/callback?token=")

    from app.models.user import User

    assert User.query.count() == 1
    assert User.query.first().id == user.id


def test_oauth_bind_rejects_subject_in_other_users_bindings(app, monkeypatch):
    """数组中的第三方账号已被他人占用时，绑定必须被拒绝。"""
    _mock_github(monkeypatch)
    _create_user(
        "owner",
        email="owner@example.com",
        oauth_provider="google",
        oauth_subject="2002",
        oauth_bindings='[{"provider": "google", "subject": "2002"}, {"provider": "github", "subject": "1001"}]',
    )
    other = _create_user("other")
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["oauth_bind_user_id"] = str(other.id)

    resp = client.get("/api/auth/oauth/github/callback")

    assert resp.status_code == 302
    assert "error=" in resp.headers["Location"]

    from app.models.user import User

    assert not User.query.get(other.id).has_oauth_binding("github", "1001")


def test_oauth_unbind_removes_single_binding(app):
    """解绑其中一个第三方账号：其余绑定保留，主绑定列自动切换。"""
    user = _create_user(
        "dual",
        email="dual@example.com",
        oauth_provider="google",
        oauth_subject="2002",
        oauth_bindings='[{"provider": "google", "subject": "2002"}, {"provider": "github", "subject": "1001"}]',
    )
    client = app.test_client()

    resp = client.delete("/api/auth/oauth/google/bind", headers=_access_token_header(user))

    assert resp.status_code == 200

    from app.models.user import User

    refreshed = User.query.get(user.id)
    assert not refreshed.has_oauth_binding("google", "2002")
    assert refreshed.has_oauth_binding("github", "1001")
    assert refreshed.oauth_provider == "github"
    assert refreshed.oauth_subject == "1001"


def test_oauth_unbind_last_binding_clears_primary(app):
    """解绑最后一个第三方账号：主绑定列清空。"""
    user = _create_user(
        "solo",
        email="solo@example.com",
        oauth_provider="github",
        oauth_subject="1001",
        oauth_bindings='[{"provider": "github", "subject": "1001"}]',
    )
    client = app.test_client()

    resp = client.delete("/api/auth/oauth/github/bind", headers=_access_token_header(user))

    assert resp.status_code == 200

    from app.models.user import User

    refreshed = User.query.get(user.id)
    assert refreshed.oauth_bindings is None
    assert refreshed.oauth_provider is None
    assert refreshed.oauth_subject is None


def test_oauth_unbind_rejects_unbound_provider(app):
    """未绑定的第三方账号不能解绑。"""
    user = _create_user("plain")
    client = app.test_client()

    resp = client.delete("/api/auth/oauth/google/bind", headers=_access_token_header(user))

    assert resp.status_code == 400
    assert "未绑定" in resp.get_json()["error"]


def test_oauth_rebind_after_unbind_goes_to_new_account(app, monkeypatch):
    """第三方账号解绑后可重新绑定到其他账号（原绑定已释放，不覆盖）。"""
    _mock_github(monkeypatch)
    first = _create_user("first", oauth_provider="github", oauth_subject="1001",
                         oauth_bindings='[{"provider": "github", "subject": "1001"}]')
    second = _create_user("second")
    client = app.test_client()

    resp = client.delete("/api/auth/oauth/github/bind", headers=_access_token_header(first))
    assert resp.status_code == 200

    with client.session_transaction() as sess:
        sess["oauth_bind_user_id"] = str(second.id)

    resp = client.get("/api/auth/oauth/github/callback")
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("http://localhost:5173/user/profile?oauth_bind=ok")

    from app.models.user import User

    assert User.query.get(second.id).has_oauth_binding("github", "1001")
    assert not User.query.get(first.id).has_oauth_binding("github", "1001")
