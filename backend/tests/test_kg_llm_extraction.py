# -*- coding: utf-8 -*-
"""LLM 知识图谱抽取与消歧测试：JSON 解析容错、正则降级、同义合并、embedding 合并。"""
import json

import pytest

from app.services.kg.entity_resolution import EntityResolver, normalize_name, resolve_triples
from app.services.kg.llm_extractor import LLMExtractor, _extract_json_array


class _FakeEmbedding:
    """模拟 embedding 服务：相同前缀的向量相似。"""

    is_degraded = False

    def encode_query(self, texts):
        import numpy as np

        return [np.zeros(8, dtype="float32") for _ in texts]


# ------------------------------------------------------------------
# JSON 解析容错
# ------------------------------------------------------------------
def test_extract_json_array_plain():
    raw = '[{"source": "A", "relation": "r", "target": "B"}]'
    parsed = _extract_json_array(raw)
    assert parsed is not None
    assert parsed[0]["source"] == "A"


def test_extract_json_array_code_fence():
    raw = '```json\n[{"source": "A", "relation": "r", "target": "B"}]\n```'
    parsed = _extract_json_array(raw)
    assert parsed is not None
    assert parsed[0]["target"] == "B"


def test_extract_json_array_with_explanation():
    raw = '以下是抽取结果：\n[{"source": "A", "relation": "r", "target": "B"}]\n仅供参考。'
    parsed = _extract_json_array(raw)
    assert parsed is not None
    assert parsed[0]["relation"] == "r"


def test_extract_json_array_invalid():
    assert _extract_json_array("不是 JSON") is None
    assert _extract_json_array("") is None


# ------------------------------------------------------------------
# 正则降级兜底
# ------------------------------------------------------------------
def test_regex_fallback_never_empty_on_security_text(monkeypatch):
    extractor = LLMExtractor(api_key="", api_base="http://x", model="m")
    text = "SQL注入和XSS是常见Web漏洞，Burp Suite可以检测，防火墙可以缓解。"
    triples = extractor.extract_from_chunk(text)
    assert triples, "正则降级不应返回空"
    assert all(t.get("relation") for t in triples)
    names = [t["source"] for t in triples] + [t["target"] for t in triples]
    assert any("SQL" in n for n in names)


def test_llm_failure_falls_back_to_regex(monkeypatch):
    extractor = LLMExtractor(api_key="fake-key", api_base="http://127.0.0.1:1", model="m")
    monkeypatch.setattr(extractor, "_call_llm", lambda chunk: None)
    triples = extractor.extract_from_chunk("SQL注入攻击，使用Nmap扫描。")
    assert triples
    assert triples[0]["_source"] == "regex"


def test_llm_parse_failure_falls_back_to_regex(monkeypatch):
    extractor = LLMExtractor(api_key="fake-key", api_base="http://x", model="m")
    monkeypatch.setattr(extractor, "_call_llm", lambda chunk: "模型输出了无法解析的内容")
    triples = extractor.extract_from_chunk("SQL注入攻击。Burp Suite 可以检测。")
    assert triples
    assert triples[0]["_source"] == "regex"


# ------------------------------------------------------------------
# 名称规范化
# ------------------------------------------------------------------
def test_normalize_name():
    assert normalize_name("  SQL 注入  ") == "SQL 注入"
    assert normalize_name("参数化查询（最佳实践）") == "参数化查询"
    assert normalize_name("") == ""


# ------------------------------------------------------------------
# 同义词合并
# ------------------------------------------------------------------
def test_synonym_merging():
    triples = [
        {"source": "SQLi", "source_type": "attack_technique", "relation": "related_to",
         "target": "XSS", "target_type": "attack_technique"},
        {"source": "SQL注入", "source_type": "attack_technique", "relation": "related_to",
         "target": "XSS", "target_type": "attack_technique"},
    ]
    cleaned, resolver = resolve_triples(triples)
    entities = resolver.entities()
    assert "SQL注入" in entities, "SQLi 应被合并为 SQL注入"
    assert entities["SQL注入"]["count"] == 2


def test_edit_distance_merging():
    triples = [
        {"source": "SQL注入", "source_type": "attack_technique", "relation": "related_to",
         "target": "XSS", "target_type": "attack_technique"},
        {"source": "SQL注人", "source_type": "attack_technique", "relation": "related_to",
         "target": "XSS", "target_type": "attack_technique"},
    ]
    cleaned, resolver = resolve_triples(triples)
    assert "SQL注入" in resolver.entities()


def test_embedding_merging():
    """embedding 相似时合并：相同向量（余弦=1）的两个不同名实体应合并为一个。"""

    class SameVecEmbedding:
        is_degraded = False

        def encode_query(self, texts):
            import numpy as np

            return [np.ones(8, dtype="float32") for _ in texts]

    triples = [
        {"source": "认证绕过", "source_type": "attack_technique", "relation": "related_to",
         "target": "XSS", "target_type": "attack_technique"},
        {"source": "身份验证绕过机制", "source_type": "attack_technique", "relation": "related_to",
         "target": "XSS", "target_type": "attack_technique"},
    ]
    cleaned, resolver = resolve_triples(triples, embedding_service=SameVecEmbedding())
    # 编辑距离大于阈值（名字不同且够长），但 embedding 向量相同 → 应合并为一个实体
    assert len(resolver.entities()) == 1, f"应合并为一个实体，实际: {list(resolver.entities())}"


def test_entity_resolution_self_loop_removed():
    triples = [
        {"source": "SQL注入", "source_type": "attack_technique", "relation": "related_to",
         "target": "SQL注入", "target_type": "attack_technique"},
    ]
    cleaned, _ = resolve_triples(triples)
    assert cleaned == [], "自环三元组应被过滤"


def test_duplicate_triples_deduplicated():
    triples = [
        {"source": "A", "source_type": "concept", "relation": "related_to",
         "target": "B", "target_type": "concept"},
        {"source": "A", "source_type": "concept", "relation": "related_to",
         "target": "B", "target_type": "concept"},
    ]
    cleaned, _ = resolve_triples(triples)
    assert len(cleaned) == 1
