# -*- coding: utf-8 -*-
"""Embedding 模型降级链测试：主模型 → 轻量备选 → 词袋兜底。"""
from __future__ import annotations

import numpy as np
import pytest

from app.services import secbert_embedding as module


class _FakeModel:
    """模拟 transformers AutoModel，不加载真实权重。"""

    class _Config:
        hidden_size = 768

    config = _Config()
    hidden_size = 768

    def __init__(self):
        self._device = None

    def to(self, device):
        self._device = device
        return self

    def eval(self):
        return self

    def __call__(self, **kwargs):
        # 返回 last_hidden_state [batch, seq, hidden]
        import torch

        batch = kwargs["input_ids"].shape[0]
        return type("Out", (), {"last_hidden_state": torch.zeros(batch, 3, self.hidden_size)})()


class _FakeTokenizer:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, texts, **kwargs):
        import torch

        return {
            "input_ids": torch.zeros(len(texts), 3, dtype=torch.long),
            "attention_mask": torch.ones(len(texts), 3, dtype=torch.long),
        }


def _make_embedding(monkeypatch, memory_mb, main_name="main-model", fallback_name="fallback-model"):
    monkeypatch.setattr(module, "TRANSFORMERS_AVAILABLE", True)
    monkeypatch.setattr(module.Config, "EMBEDDING_MODEL", main_name)
    monkeypatch.setattr(module.Config, "EMBEDDING_FALLBACK_MODEL", fallback_name)
    monkeypatch.setattr(module.Config, "EMBEDDING_MIN_FREE_MEMORY_MB", 4096)
    monkeypatch.setattr(module.Config, "EMBEDDING_FALLBACK_MIN_FREE_MEMORY_MB", 1500)
    monkeypatch.setattr(module.Config, "HF_ENDPOINT", "https://hf-mirror.com")
    monkeypatch.setattr(module.Config, "EMBEDDING_DIMENSION", 1024)

    loaded = {}

    def fake_from_pretrained(name, **kwargs):
        if name in ("main-model", "fallback-model"):
            loaded[name] = True
            return _FakeModel()
        raise RuntimeError(f"unexpected model {name}")

    monkeypatch.setattr(module.AutoTokenizer, "from_pretrained", staticmethod(lambda name, **kw: _FakeTokenizer()))
    monkeypatch.setattr(module.AutoModel, "from_pretrained", staticmethod(fake_from_pretrained))

    def fake_memory():
        return memory_mb

    monkeypatch.setattr(module.SecBERTEmbedding, "_system_memory_mb", staticmethod(fake_memory))

    service = module.SecBERTEmbedding(model_name=main_name, device="cpu")
    return service, loaded


def test_main_model_loaded_when_memory_plenty(monkeypatch):
    """内存充足时加载主模型，不降级。"""
    service, loaded = _make_embedding(monkeypatch, memory_mb=8192)
    assert loaded == {"main-model": True}
    assert service.model_name == "main-model"
    assert service.is_degraded is False
    assert service.get_embedding_dimension() == 768


def test_fallback_model_loaded_when_memory_low(monkeypatch):
    """内存不足主模型时，回退轻量备选模型，仍标记降级（维度不同）。"""
    service, loaded = _make_embedding(monkeypatch, memory_mb=2000)
    assert loaded == {"fallback-model": True}
    assert service.model_name == "fallback-model"
    assert service.is_degraded is True
    assert service.get_embedding_dimension() == 768

    # 轻量模型 encode 走真实模型路径（非词袋）
    vec = service.encode(["hello world"])
    assert vec.shape[1] == 768
    assert service.model is not None


def test_bag_of_words_fallback_when_memory_very_low(monkeypatch):
    """内存连备选模型都不足时，回退词袋兜底。"""
    service, loaded = _make_embedding(monkeypatch, memory_mb=500)
    assert loaded == {}
    assert service.model is None
    assert service.is_degraded is True

    vec = service.encode(["hello world"])
    assert vec.shape[1] == module.Config.EMBEDDING_DIMENSION


def test_fallback_model_when_main_load_fails(monkeypatch):
    """主模型加载抛异常（即使内存充足）时回退备选模型。"""
    monkeypatch.setattr(module, "TRANSFORMERS_AVAILABLE", True)
    monkeypatch.setattr(module.Config, "EMBEDDING_MODEL", "main-model")
    monkeypatch.setattr(module.Config, "EMBEDDING_FALLBACK_MODEL", "fallback-model")
    monkeypatch.setattr(module.Config, "EMBEDDING_MIN_FREE_MEMORY_MB", 4096)
    monkeypatch.setattr(module.Config, "EMBEDDING_FALLBACK_MIN_FREE_MEMORY_MB", 1500)
    monkeypatch.setattr(module.Config, "HF_ENDPOINT", "https://hf-mirror.com")
    monkeypatch.setattr(module.Config, "EMBEDDING_DIMENSION", 1024)
    monkeypatch.setattr(module.AutoTokenizer, "from_pretrained", staticmethod(lambda name, **kw: _FakeTokenizer()))
    monkeypatch.setattr(module.SecBERTEmbedding, "_system_memory_mb", staticmethod(lambda: 8192))

    loaded = {}

    def fake_from_pretrained(name, **kwargs):
        if name == "main-model":
            raise RuntimeError("main model corrupted")
        loaded[name] = True
        return _FakeModel()

    monkeypatch.setattr(module.AutoModel, "from_pretrained", staticmethod(fake_from_pretrained))

    service = module.SecBERTEmbedding(model_name="main-model", device="cpu")
    assert loaded == {"fallback-model": True}
    assert service.model_name == "fallback-model"
    assert service.is_degraded is True


def test_no_fallback_configured_uses_bag_of_words(monkeypatch):
    """未配置备选模型时，主模型失败直接词袋兜底。"""
    monkeypatch.setattr(module, "TRANSFORMERS_AVAILABLE", True)
    monkeypatch.setattr(module.Config, "EMBEDDING_MODEL", "main-model")
    monkeypatch.setattr(module.Config, "EMBEDDING_FALLBACK_MODEL", "")
    monkeypatch.setattr(module.Config, "EMBEDDING_MIN_FREE_MEMORY_MB", 4096)
    monkeypatch.setattr(module.Config, "EMBEDDING_FALLBACK_MIN_FREE_MEMORY_MB", 1500)
    monkeypatch.setattr(module.Config, "HF_ENDPOINT", "https://hf-mirror.com")
    monkeypatch.setattr(module.Config, "EMBEDDING_DIMENSION", 1024)
    monkeypatch.setattr(module.AutoTokenizer, "from_pretrained", staticmethod(lambda name, **kw: _FakeTokenizer()))
    monkeypatch.setattr(module.AutoModel, "from_pretrained", staticmethod(lambda name, **kw: (_ for _ in ()).throw(RuntimeError("no model"))))
    monkeypatch.setattr(module.SecBERTEmbedding, "_system_memory_mb", staticmethod(lambda: 8192))

    service = module.SecBERTEmbedding(model_name="main-model", device="cpu")
    assert service.model is None
    assert service.is_degraded is True
    vec = service.encode(["anything"])
    assert vec.shape[1] == module.Config.EMBEDDING_DIMENSION


def test_fallback_dimension_matches_loaded_model(monkeypatch):
    """备选模型维度取实际模型 hidden_size，而不是主模型配置维度。"""
    service, _ = _make_embedding(monkeypatch, memory_mb=2000)
    assert service.get_embedding_dimension() == 768
    assert module.Config.EMBEDDING_DIMENSION == 1024
