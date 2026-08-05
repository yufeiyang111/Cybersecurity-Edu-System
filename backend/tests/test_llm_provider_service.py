import os

import pytest
from cryptography.fernet import Fernet

from app import db
from app.models.llm import LLMProviderConfig
from app.models.user import User
from app.services.llm.provider_service import validate_provider_url
from app.services.llm.secrets import decrypt_secret, encrypt_secret, mask_secret


def _make_user(username: str) -> User:
    user = User(username=username, email=f"{username}@example.test", password_hash="x")
    db.session.add(user)
    db.session.flush()
    return user


def test_provider_to_dict_never_returns_ciphertext_or_plaintext(app):
    with app.app_context():
        provider = LLMProviderConfig(
            user_id=1,
            name="private",
            base_url="https://llm.example/v1",
            model="private-model",
            api_key_ciphertext="ciphertext-only",
            api_key_hint="••••1234",
        )

        payload = provider.to_dict()

        assert payload["api_key_masked"] == "••••1234"
        assert "api_key_ciphertext" not in payload
        assert "ciphertext-only" not in repr(payload)


def test_encrypt_secret_requires_configured_master_key(app, monkeypatch):
    with app.app_context():
        monkeypatch.delenv("LLM_PROVIDER_ENCRYPTION_KEY", raising=False)
        app.config["LLM_PROVIDER_ENCRYPTION_KEY"] = ""

        with pytest.raises(RuntimeError, match="encryption key"):
            encrypt_secret("private-api-key")


def test_encrypt_secret_round_trips_with_fernet_key(app):
    with app.app_context():
        app.config["LLM_PROVIDER_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")

        ciphertext = encrypt_secret("private-api-key")

        assert ciphertext != "private-api-key"
        assert decrypt_secret(ciphertext) == "private-api-key"
        assert mask_secret("sk-test-1234567890") == "sk-te••••7890"


def test_provider_model_is_user_scoped_and_unique_by_name(app):
    with app.app_context():
        first = _make_user("llm-first")
        second = _make_user("llm-second")
        db.session.add(
            LLMProviderConfig(
                user_id=first.id,
                name="private",
                base_url="https://llm.example/v1",
                model="private-model",
                api_key_ciphertext="ciphertext",
                api_key_hint="••••1234",
            )
        )
        db.session.commit()

        assert LLMProviderConfig.query.filter_by(user_id=first.id, name="private").one()
        assert LLMProviderConfig.query.filter_by(user_id=second.id, name="private").first() is None


@pytest.mark.parametrize(
    "value",
    [None, "", "  "],
)
def test_mask_secret_handles_empty_values(value):
    assert mask_secret(value) == "未配置"


@pytest.mark.parametrize(
    "value",
    [
        "http://169.254.169.254/latest/meta-data",
        "https://user:pass@llm.example/v1",
        "https://llm.example/v1?token=secret",
        "https://llm.example/v1#secret",
    ],
)
def test_provider_url_rejects_ssrf_or_embedded_credentials(value):
    with pytest.raises(ValueError):
        validate_provider_url(value, allowed_hosts=[])


def test_provider_url_allows_explicit_private_host_and_normalizes_path():
    assert (
        validate_provider_url(
            "http://llm.internal:8000/v1/",
            allowed_hosts=["llm.internal:8000"],
        )
        == "http://llm.internal:8000/v1"
    )


@pytest.mark.parametrize("value", ["ftp://llm.example/v1", "not-a-url", "http://localhost:8000/v1"])
def test_provider_url_rejects_invalid_protocol_or_blocked_host(value):
    with pytest.raises(ValueError):
        validate_provider_url(value, allowed_hosts=[])


def test_provider_service_rejects_invalid_name_and_model_before_encryption(app):
    from app.services.llm.provider_service import create_for_user

    with app.app_context():
        with pytest.raises(ValueError, match="name"):
            create_for_user(
                1,
                {"name": "x" * 101, "base_url": "https://llm.example/v1", "model": "m", "api_key": "key"},
                allowed_hosts=[],
            )
        with pytest.raises(ValueError, match="model"):
            create_for_user(
                1,
                {"name": "private", "base_url": "https://llm.example/v1", "model": "", "api_key": "key"},
                allowed_hosts=[],
            )
