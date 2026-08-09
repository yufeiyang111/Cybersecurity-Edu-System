# -*- coding: utf-8 -*-
"""LLM provider 选择保底机制测试。

保底要求：用户未配置（或查询失败）时，必须回退到系统 env 配置的服务端 provider，
任何查询异常不得阻断兜底（siliconflow 仅限 embedding/rerank，LLM 一律用户私有或系统 MiniMax）。
"""
from __future__ import annotations

import pytest

from app.services.llm import provider_selector


@pytest.fixture
def app_ctx():
    from app import create_app

    app = create_app()
    with app.app_context():
        yield app


class _FakeFallback:
    """模拟系统兜底 provider（env MiniMax）。"""


class _FakeUserConfig:
    name = "private"
    base_url = "http://private.local/v1"
    api_key_ciphertext = "ciphertext"
    model = "private-model"
    id = 7


class _FakePrivateProvider:
    pass


def test_select_provider_falls_back_when_user_lookup_fails(app_ctx, monkeypatch):
    """用户 provider 查询抛异常时，必须继续回退系统 provider（保底不失效）。"""

    def boom(user_id):
        raise RuntimeError("db down")

    monkeypatch.setattr(provider_selector, "get_default_for_user", boom)
    monkeypatch.setattr(
        provider_selector, "select_configured_provider", lambda: _FakeFallback()
    )
    monkeypatch.setattr(provider_selector, "observe_provider", lambda p, **kw: p)

    provider = provider_selector.select_provider(user_id=13, operation="memory")
    assert isinstance(provider, _FakeFallback)


def test_select_provider_falls_back_when_no_user_provider(app_ctx, monkeypatch):
    """用户未配置任何 provider 时，回退系统 provider。"""
    monkeypatch.setattr(provider_selector, "get_default_for_user", lambda uid: None)
    monkeypatch.setattr(
        provider_selector, "select_configured_provider", lambda: _FakeFallback()
    )
    monkeypatch.setattr(provider_selector, "observe_provider", lambda p, **kw: p)

    provider = provider_selector.select_provider(user_id=13, operation="memory")
    assert isinstance(provider, _FakeFallback)


def test_select_provider_uses_user_provider_first(app_ctx, monkeypatch):
    """用户配置了私有 provider 时优先使用，不走到系统兜底。"""
    monkeypatch.setattr(
        provider_selector, "get_default_for_user", lambda uid: _FakeUserConfig()
    )
    monkeypatch.setattr(provider_selector, "decrypt_secret", lambda c: "key")
    monkeypatch.setattr(
        provider_selector,
        "OpenAICompatibleProvider",
        lambda **kw: _FakePrivateProvider(),
    )
    monkeypatch.setattr(provider_selector, "observe_provider", lambda p, **kw: p)
    called = {"fallback": False}

    def fallback():
        called["fallback"] = True
        return _FakeFallback()

    monkeypatch.setattr(provider_selector, "select_configured_provider", fallback)

    provider = provider_selector.select_provider(user_id=13, operation="memory")
    assert isinstance(provider, _FakePrivateProvider)
    assert called["fallback"] is False


def test_select_provider_user_provider_load_failure_falls_back(app_ctx, monkeypatch):
    """用户 provider 创建失败（密钥解密等）时回退系统 provider。"""
    monkeypatch.setattr(
        provider_selector, "get_default_for_user", lambda uid: _FakeUserConfig()
    )
    monkeypatch.setattr(provider_selector, "decrypt_secret", lambda c: _boom())

    def _boom():
        raise ValueError("bad cipher")

    monkeypatch.setattr(provider_selector, "decrypt_secret", lambda c: _boom())
    monkeypatch.setattr(
        provider_selector, "select_configured_provider", lambda: _FakeFallback()
    )
    monkeypatch.setattr(provider_selector, "observe_provider", lambda p, **kw: p)

    provider = provider_selector.select_provider(user_id=13, operation="memory")
    assert isinstance(provider, _FakeFallback)
