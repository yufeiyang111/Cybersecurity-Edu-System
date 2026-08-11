# -*- coding: utf-8 -*-
"""图谱抽取断点续传测试：落盘/恢复/跳过已完成文档/额度中断保留断点。"""
import json

import pytest

from app.services.kg.builder import KnowledgeGraphLLMBuilder, _split_text
from app.services.kg.checkpoint import CheckpointStore
from app.services.kg.llm_extractor import QuotaExhaustedError


# ------------------------------------------------------------------
# 文本分块
# ------------------------------------------------------------------
def test_split_text_small_text_single_chunk():
    assert _split_text("短文本") == ["短文本"]
    assert _split_text("") == []


def test_split_text_long_text_multi_chunk():
    para = "这是一个段落。" * 100  # 1200 字符
    chunks = _split_text(para, max_chars=500)
    assert len(chunks) >= 2
    assert all(len(c) <= 500 for c in chunks)
    assert "".join(chunks) == para


# ------------------------------------------------------------------
# CheckpointStore
# ------------------------------------------------------------------
def test_checkpoint_roundtrip(tmp_path):
    path = str(tmp_path / "ckpt.json")
    store = CheckpointStore(path)
    store.save(["1", "2"], [{"a": 1}], {"prompt_tokens": 10, "completion_tokens": 5})
    data = store.load()
    assert data["completed_docs"] == ["1", "2"]
    assert data["triples"] == [{"a": 1}]
    assert data["usage"]["prompt_tokens"] == 10
    assert store.exists()


def test_checkpoint_missing_returns_empty(tmp_path):
    store = CheckpointStore(str(tmp_path / "none.json"))
    assert not store.exists()
    data = store.load()
    assert data["completed_docs"] == []
    assert data["triples"] == []
    assert data["usage"]["prompt_tokens"] == 0


def test_checkpoint_clear(tmp_path):
    path = str(tmp_path / "ckpt.json")
    store = CheckpointStore(path)
    store.save(["1"], [], {"prompt_tokens": 0, "completion_tokens": 0})
    assert store.exists()
    store.clear()
    assert not store.exists()


def test_checkpoint_corrupt_returns_empty(tmp_path):
    path = str(tmp_path / "ckpt.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write("{broken json")
    store = CheckpointStore(path)
    data = store.load()
    assert data["completed_docs"] == []


# ------------------------------------------------------------------
# Builder：断点续传
# ------------------------------------------------------------------
class _FakeExtractor:
    """可控抽取器：记录传入文本（含文档标题），可触发额度耗尽。"""

    def __init__(self, triples_by_text, fail_on_text=None):
        self.triples_by_text = triples_by_text
        self.called_texts = []
        self.fail_on_text = fail_on_text

    def extract_batch(self, texts):
        results = []
        for text in texts:
            if self.fail_on_text is not None and self.fail_on_text in text:
                raise QuotaExhaustedError("额度耗尽")
            self.called_texts.append(text)
            results.append(self.triples_by_text.get(text, []))
        return results


def _make_items(count=5):
    return [
        {"id": i, "title": f"标题{i}", "content": "网络安全知识内容" * 30,
         "category_name": "测试", "tags": []}
        for i in range(1, count + 1)
    ]


class _FakeGraph:
    def __init__(self):
        self.knowledge_nodes = []
        self.entities = []
        self.relations = []

    def add_knowledge_node(self, **kwargs):
        self.knowledge_nodes.append(kwargs)

    def add_entity(self, **kwargs):
        self.entities.append(kwargs)

    def add_relation(self, **kwargs):
        self.relations.append(kwargs)


class _FakeEmbedding:
    is_degraded = True  # 跳过 embedding 消歧，走字符串合并


def test_builder_resume_skips_completed(tmp_path):
    """resume 时跳过已完成文档，只抽取剩余文档。"""
    items = _make_items(5)
    triple = [{"source": "A", "source_type": "concept", "relation": "related_to",
               "target": "B", "target_type": "concept", "confidence": 0.9}]
    extractor = _FakeExtractor(triples_by_text={})
    # 预置断点：doc 1 已完成
    ckpt_path = str(tmp_path / "ckpt.json")
    store = CheckpointStore(ckpt_path)
    store.save(["1"], [], {"prompt_tokens": 100, "completion_tokens": 50})

    builder = KnowledgeGraphLLMBuilder(
        extractor=extractor, graph=_FakeGraph(), embedding_service=_FakeEmbedding()
    )
    report = builder.build(items, checkpoint_path=ckpt_path, resume=True)
    # doc 1 跳过 → 剩余 4 篇被抽取（每篇 1 块）
    assert len(extractor.called_texts) == 4
    assert not any("标题1" in t for t in extractor.called_texts), "标题1 的文档应被跳过"
    assert any("标题2" in t for t in extractor.called_texts)
    assert report["resumed_docs"] == 1
    # 完成后断点被清理
    assert not store.exists()


def test_builder_quota_exhausted_keeps_checkpoint(tmp_path):
    """额度耗尽时抛异常，断点保留，已完成文档不浪费。"""
    # 40 篇文档 → 超过 BATCH_SIZE(18) 触发多批调用
    items = _make_items(40)

    class QuotaExtractor:
        def __init__(self):
            self.calls = 0

        def extract_batch(self, texts):
            self.calls += 1
            if self.calls == 1:
                return [[{"source": "A", "source_type": "concept", "relation": "related_to",
                          "target": "B", "target_type": "concept", "confidence": 0.9}] for _ in texts]
            raise QuotaExhaustedError("额度耗尽")

    ckpt_path = str(tmp_path / "ckpt.json")
    builder = KnowledgeGraphLLMBuilder(
        extractor=QuotaExtractor(), graph=_FakeGraph(), embedding_service=_FakeEmbedding()
    )
    with pytest.raises(QuotaExhaustedError):
        builder.build(items, checkpoint_path=ckpt_path, resume=False)
    store = CheckpointStore(ckpt_path)
    assert store.exists(), "额度耗尽后断点应保留"
    data = store.load()
    assert len(data["completed_docs"]) >= 1
    assert data["triples"], "已抽取的三元组应保存在断点"


def test_builder_no_checkpoint_path_still_works(tmp_path):
    """不传 checkpoint_path 时正常构建（兼容旧调用）。"""
    items = _make_items(2)
    triple = [{"source": "A", "source_type": "concept", "relation": "related_to",
               "target": "B", "target_type": "concept", "confidence": 0.9}]
    extractor = _FakeExtractor(triples_by_text={})
    builder = KnowledgeGraphLLMBuilder(
        extractor=extractor, graph=_FakeGraph(), embedding_service=_FakeEmbedding()
    )
    report = builder.build(items)
    assert report["documents_processed"] == 2
    assert "usage_tokens" in report
