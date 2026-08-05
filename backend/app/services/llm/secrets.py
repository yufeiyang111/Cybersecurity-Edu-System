"""Encryption and redaction helpers for user-managed LLM credentials."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _cipher() -> Fernet:
    configured_key = str(current_app.config.get("LLM_PROVIDER_ENCRYPTION_KEY", "") or "").strip()
    if not configured_key:
        raise RuntimeError("LLM provider encryption key is not configured")
    try:
        return Fernet(configured_key.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise RuntimeError("LLM provider encryption key is invalid") from exc


def encrypt_secret(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("API Key 不能为空")
    return _cipher().encrypt(normalized.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        raise ValueError("加密的 API Key 为空")
    try:
        return _cipher().decrypt(str(value).encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("LLM provider secret cannot be decrypted") from exc


def mask_secret(value: str | None) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return "未配置"
    if len(normalized) <= 8:
        return "*" * len(normalized)
    return f"{normalized[:5]}••••{normalized[-4:]}"
