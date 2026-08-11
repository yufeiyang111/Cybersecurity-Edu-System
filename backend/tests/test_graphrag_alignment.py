# -*- coding: utf-8 -*-
"""GraphRAG 对齐测试：实体 description、共享 LLM client、全局/局部检索、描述回填、增量索引。"""
import json
import threading
import time

import networkx as nx
import pytest

from app.services.kg.entity_resolution import EntityResolver, resolve_triples
from app.services.kg.llm_extractor import EXTRACTION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# 1. 实体 description：抽取 prompt / 消歧合并 / builder 透传
# ---------------------------------------------------------------------------
def test_extraction_prompt_requires_description():
    assert "source_description" in EXTRACTION_SYSTEM_PROMPT
    assert "target_description" in EXTRACTION_SYSTEM_PROMPT


def test_resolver_merges_description():
    resolver = EntityResolver()
    resolver.add_triples([
        {"source": "SQL注入", "source_type": "attack_technique",
         "source_description": "向数据库查询拼接恶意SQL的攻击手法", "target": "数据库",
         "target_type": "concept", "target_description": "存储数据的系统"},
        {"source": "sqli", "source_type": "attack_technique",
         "source_description": "短描述", "target": "数据库",
         "target_type": "concept", "target_description": ""},
    ])
    entities = resolver.entities()
    sql = next(v for k, v in entities.items() if v["type"] == "attack_technique")
    assert sql["description"] == "向数据库查询拼接恶意SQL的攻击手法", "应保留更长/首次描述"
    db = next(v for k, v in entities.items() if k == "数据库")
    assert db["description"] == "存储数据的系统"


def test_resolver_keeps_existing_description_when_new_is_shorter():
    resolver = EntityResolver()
    resolver.add_triples([
        {"source": "XSS", "source_type": "attack_technique",
         "source_description": "跨站脚本攻击，向网页注入恶意脚本", "target": "A",
         "target_type": "concept", "target_description": "a"},
        {"source": "XSS", "source_type": "attack_technique",
         "source_description": "短", "target": "B",
         "target_type": "concept", "target_description": "b"},
    ])
    entities = resolver.entities()
    xss = next(v for k, v in entities.items() if v["type"] == "attack_technique")
    assert xss["description"] == "跨站脚本攻击，向网页注入恶意脚本"


def test_resolve_triples_keeps_description_in_entities():
    triples = [
        {"source": "mimikatz", "source_type": "security_tool",
         "source_description": "Windows凭证窃取工具", "target": "LSASS",
         "target_type": "concept", "target_description": "存储登录凭证的进程",
         "relation": "exploits", "confidence": 0.9, "_source": "llm"},
    ]
    cleaned, resolver = resolve_triples(triples)
    assert len(cleaned) == 1
    entities = resolver.entities()
    assert any(v["description"] == "Windows凭证窃取工具" for v in entities.values())


def test_builder_passes_description_to_add_entity(monkeypatch):
    """builder 入库时应把 description 传给 add_entity properties。"""
    from app.services.kg.builder import KnowledgeGraphLLMBuilder

    captured = []

    class FakeGraph:
        def add_knowledge_node(self, **kwargs):
            pass

        def add_entity(self, entity_id, name, entity_type, properties):
            captured.append(properties)

        def add_relation(self, **kwargs):
            pass

    class FakeExtractor:
        usage = {"prompt_tokens": 1, "completion_tokens": 1}

        def extract_batch(self, texts):
            return [[{
                "source": "mimikatz", "source_type": "security_tool",
                "source_description": "Windows凭证窃取工具",
                "target": "LSASS", "target_type": "concept",
                "target_description": "存储登录凭证的进程",
                "relation": "exploits", "confidence": 0.9, "_source": "llm",
            }] for _ in texts]

    class FakeEmbedding:
        is_degraded = True

    builder = KnowledgeGraphLLMBuilder(
        extractor=FakeExtractor(), graph=FakeGraph(),
        embedding_service=FakeEmbedding(),
    )
    builder.build([{"id": 1, "title": "t", "content": "c"}])
    props = {p["description"] for p in captured if "description" in p}
    assert "Windows凭证窃取工具" in props


# ---------------------------------------------------------------------------
# 2. 共享 LLM Provider client
# ---------------------------------------------------------------------------
def test_llm_provider_client_quota_switch(monkeypatch):
    from app.services.kg.llm_extractor import QuotaExhaustedError
    from app.services.kg.llm_provider import LLMProviderClient

    client = LLMProviderClient()
    calls = []
    client.providers = [
        {"name": "minimax", "api_key": "k1", "api_base": "http://x", "model": "m1",
         "endpoint": "chatcompletion_v2"},
        {"name": "fallback", "api_key": "k2", "api_base": "http://y", "model": "m2",
         "endpoint": "chat/completions"},
    ]

    def fake_post(url, headers, json, timeout):
        calls.append(json["model"])
        if "x" in url:
            raise QuotaExhaustedError("quota")
        return type("R", (), {
            "status_code": 200, "text": "",
            "json": (lambda self: {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }),
        })()

    monkeypatch.setattr(client._session, "post", fake_post)
    result = client.call("hello")
    assert result == "ok"
    assert calls == ["m1", "m2"], "额度耗尽应切换到备用 provider"
    assert client.usage["prompt_tokens"] == 10


def test_llm_provider_client_all_quota_raises(monkeypatch):
    from app.services.kg.llm_extractor import QuotaExhaustedError
    from app.services.kg.llm_provider import LLMProviderClient

    client = LLMProviderClient()
    client.providers = [
        {"name": "p1", "api_key": "k", "api_base": "http://x", "model": "m",
         "endpoint": "chat/completions"},
    ]

    def fake_post(url, headers, json, timeout):
        raise QuotaExhaustedError("quota")

    monkeypatch.setattr(client._session, "post", fake_post)
    with pytest.raises(QuotaExhaustedError):
        client.call("hello")


# ---------------------------------------------------------------------------
# 3. GraphRAG Global Search（社区摘要 Map-Reduce）
# ---------------------------------------------------------------------------
def test_global_search_without_summaries(app, monkeypatch):
    from app.services.kg.graphrag_search import GraphRagSearcher

    searcher = GraphRagSearcher()
    # 无社区摘要 → 返回提示
    result = searcher.global_search("什么是SQL注入", top_k=5)
    assert result["mode"] == "global"
    assert "暂无社区摘要" in result["answer"] or not result["used_communities"]


def test_global_search_map_reduce(app, monkeypatch):
    from app.services.kg.community_summarizer import CommunitySummarizer
    from app.services.kg.graphrag_search import GraphRagSearcher

    # 预置两个社区摘要
    g = nx.DiGraph()
    for i in range(1, 11):
        g.add_node(f"n{i}", type="concept", title=f"Node{i}")
    for i in range(1, 10):
        g.add_edge(f"n{i}", f"n{i + 1}", relation="related_to", weight=1.0)

    class FakeGraph:
        use_neo4j = False
        _neo4j_graph = None
        graph = g

    monkeypatch.setattr(
        "app.services.kg.graphrag_search.get_knowledge_graph", lambda: FakeGraph()
    )

    class FakeDetector:
        def detect(self, graph_data):
            return {
                "communities": {
                    "0": {"size": 10, "nodes": [f"n{i}" for i in range(1, 11)],
                          "sample": ["n1"]},
                },
                "node_community": {f"n{i}": "0" for i in range(1, 11)},
                "community_count": 1,
                "algorithm": "leiden",
            }

    monkeypatch.setattr(
        "app.services.kg.graphrag_search.get_community_detector",
        lambda: FakeDetector(),
    )

    summarizer = CommunitySummarizer()
    # 直接写 DB 缓存（绕过 LLM）
    payload = {
        "title": "SQL注入攻击", "summary": "该社区聚焦SQL注入攻击与防护。",
        "key_topics": ["SQL注入"], "representative_entities": [],
        "key_relationships": [], "security_implications": "", "defensive_measures": [],
    }
    from app.models.knowledge_graph import KnowledgeGraphCommunitySummary

    with app.app_context():
        row = KnowledgeGraphCommunitySummary(community_id="0", graph_signature="10:9",
                                             algorithm="leiden", title="SQL注入攻击",
                                             summary="该社区聚焦SQL注入攻击与防护。",
                                             summary_json=payload)
        from app import db

        db.session.add(row)
        db.session.commit()

    searcher = GraphRagSearcher()

    def fake_call(user_content, system_prompt=None, temperature=None, max_tokens=None):
        if system_prompt and "综合分析" in system_prompt:
            return "最终答案：SQL注入通过在输入中拼接恶意SQL片段达成越权查询。"
        if "社区报告" in user_content:
            return json.dumps([{
                "community_id": "0", "relevant": True,
                "answer": "SQL注入是向数据库查询拼接恶意SQL的攻击手法。",
            }], ensure_ascii=False)
        return None

    monkeypatch.setattr(searcher._client, "call", fake_call)
    with app.app_context():
        result = searcher.global_search("什么是SQL注入", top_k=5)
    assert result["used_communities"], "应使用已有摘要的社区"
    assert result["intermediate"][0]["community_id"] == "0"
    assert "最终答案" in result["answer"]


# ---------------------------------------------------------------------------
# 4. GraphRAG Local Search
# ---------------------------------------------------------------------------
def test_local_search_no_match(app, monkeypatch):
    from app.services.kg.graphrag_search import GraphRagSearcher

    searcher = GraphRagSearcher()
    g = nx.DiGraph()
    g.add_node("concept:abc", type="concept", title="abc")
    g.add_edge("concept:abc", "concept:abc")  # 无关图

    monkeypatch.setattr(searcher, "_match_entities", lambda q, t: [])
    monkeypatch.setattr(searcher, "_match_entities_networkx", lambda graph, q, t: [])
    result = searcher.local_search("完全不存在的实体XYZ")
    assert result["mode"] == "local"
    assert "没有找到" in result["answer"]


def test_local_search_with_entities(app, monkeypatch):
    from app.services.kg.graphrag_search import GraphRagSearcher

    g = nx.DiGraph()
    g.add_node("attack_technique:SQL注入", type="attack_technique", title="SQL注入",
               description="向数据库查询拼接恶意SQL")
    g.add_node("vulnerability:SQL注入漏洞", type="vulnerability", title="SQL注入漏洞",
               description="Web应用未过滤输入导致")
    g.add_node("security_tool:sqlmap", type="security_tool", title="sqlmap",
               description="自动化SQL注入检测工具")
    g.add_edge("attack_technique:SQL注入", "security_tool:sqlmap", relation="uses", weight=1.0)
    g.add_edge("vulnerability:SQL注入漏洞", "attack_technique:SQL注入",
               relation="exploits", weight=1.0)

    class FakeGraph:
        use_neo4j = False
        _neo4j_graph = None
        graph = g

    monkeypatch.setattr(
        "app.services.kg.graphrag_search.get_knowledge_graph", lambda: FakeGraph()
    )

    searcher = GraphRagSearcher()
    monkeypatch.setattr(
        searcher, "_match_entities",
        lambda q, t: [
            {"id": "attack_technique:SQL注入", "name": "SQL注入",
             "type": "attack_technique", "description": "向数据库查询拼接恶意SQL",
             "degree": 2},
        ],
    )
    monkeypatch.setattr(searcher, "_community_summaries_for", lambda e: [])
    monkeypatch.setattr(
        searcher._client, "call",
        lambda ctx, **kw: "SQL注入通过在用户输入中拼接恶意SQL片段，配合sqlmap等工具可自动化利用。",
    )

    result = searcher.local_search("SQL注入怎么利用", max_depth=2)
    assert result["entities"], "应匹配到实体"
    assert result["relationships"], "应扩展到邻居关系"
    assert "sqlmap" in str(result["relationships"]), "邻居应包含 sqlmap"
    assert "SQL注入" in result["answer"]


def test_query_keywords():
    from app.services.kg.graphrag_search import GraphRagSearcher

    kws = GraphRagSearcher._query_keywords("什么是SQL注入攻击？")
    assert any("SQL注入" in k or "SQL注入" == k for k in kws)
    kws2 = GraphRagSearcher._query_keywords("如何防御 XSS 攻击")
    assert any("XSS" in k for k in kws2)
    assert "如何" not in kws2, "停用词应被过滤"


# ---------------------------------------------------------------------------
# 5. 描述回填服务
# ---------------------------------------------------------------------------
def test_backfill_parse_batch():
    from app.services.kg.description_backfill import DescriptionBackfillService

    raw = (
        "```json\n"
        '[{"name": "mimikatz", "description": "Windows凭证窃取工具"}, '
        '{"name": "X", "description": ""}]\n'
        "```\n"
    )
    parsed = DescriptionBackfillService._parse_batch(raw)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "mimikatz"


def test_backfill_invalid_json_returns_empty():
    from app.services.kg.description_backfill import DescriptionBackfillService

    assert DescriptionBackfillService._parse_batch("无法生成") == []


def test_backfill_service_run_with_mocks(monkeypatch):
    """回填全流程：mock Neo4j 实体加载/写回 + LLM。"""
    from app.services.kg.description_backfill import (
        BATCH_SIZE,
        DescriptionBackfillService,
    )

    service = DescriptionBackfillService()
    fake_entities = [
        {"id": f"concept:e{i}", "name": f"实体{i}", "type": "concept"}
        for i in range(BATCH_SIZE + 3)
    ]

    def fake_load(limit):
        return fake_entities[:limit]

    written = {}

    def fake_update(updates):
        written.update(updates)

    monkeypatch.setattr(service, "_load_entities", fake_load)
    monkeypatch.setattr(service, "_update_descriptions", fake_update)

    class FakeClient:
        usage = {"prompt_tokens": 100, "completion_tokens": 50}

        def call(self, content, **kwargs):
            names = [line.split("（")[0][2:] for line in content.splitlines() if line.startswith("- ")]
            return json.dumps(
                [{"name": n, "description": f"{n}的描述"} for n in names],
                ensure_ascii=False,
            )

    monkeypatch.setattr(
        "app.services.kg.description_backfill.get_llm_provider_client",
        lambda: FakeClient(),
    )
    report = service._backfill(limit=BATCH_SIZE + 3, force=False)
    assert report["total_entities"] == BATCH_SIZE + 3
    assert report["updated_entities"] == BATCH_SIZE + 3
    assert len(written) == BATCH_SIZE + 3
    assert report["usage_tokens"] == 150


def test_backfill_batch_failure_skipped(monkeypatch):
    from app.services.kg.description_backfill import DescriptionBackfillService

    service = DescriptionBackfillService()
    monkeypatch.setattr(service, "_load_entities", lambda limit: [
        {"id": "concept:a", "name": "A", "type": "concept"},
        {"id": "concept:b", "name": "B", "type": "concept"},
    ])
    monkeypatch.setattr(service, "_update_descriptions", lambda u: None)

    class FailingClient:
        usage = {"prompt_tokens": 0, "completion_tokens": 0}

        def call(self, content, **kwargs):
            return None

    monkeypatch.setattr(
        "app.services.kg.description_backfill.get_llm_provider_client",
        lambda: FailingClient(),
    )
    report = service._backfill(limit=10, force=False)
    assert report["updated_entities"] == 0
    assert report["failed_batches"] > 0


# ---------------------------------------------------------------------------
# 6. 增量索引器
# ---------------------------------------------------------------------------
def test_incremental_indexer_import_and_status(monkeypatch):
    from app.services.kg.incremental_indexer import IncrementalIndexer

    monkeypatch.setattr(
        "app.services.kg.builder.build_knowledge_graph_llm",
        lambda items, progress_callback=None: {
            "nodes_added": 2, "edges_added": 3, "usage_tokens": 5,
        },
    )

    indexer = IncrementalIndexer()
    indexer.on_knowledge_imported([{"id": 1, "title": "t", "content": "c"}])
    status = indexer.status()
    assert status["queued_items"] == 1
    # 等待后台线程完成（最多 5 秒）
    deadline = time.time() + 5
    while time.time() < deadline:
        status = indexer.status()
        if status["status"] in ("success", "error"):
            break
        time.sleep(0.1)
    assert status["status"] == "success", "后台线程应完成增量构建"
    assert status["processed_items"] == 1
    assert status["nodes_added"] == 2


def test_incremental_indexer_delete_calls_graph_store(monkeypatch):
    from app.services.kg.incremental_indexer import IncrementalIndexer

    indexer = IncrementalIndexer()
    removed = []

    class FakeGraph:
        def remove_knowledge_node(self, doc_id):
            removed.append(doc_id)
            return True

        def _invalidate_sync(self):
            pass

    monkeypatch.setattr(
        "app.services.graph_store.get_knowledge_graph",
        lambda: FakeGraph(),
    )
    monkeypatch.setattr(
        "app.services.graph_communities.get_community_detector",
        lambda: type("D", (), {"invalidate": lambda self: None})(),
    )
    indexer.on_knowledge_deleted("42")
    assert removed == ["42"]


def test_graph_store_remove_knowledge_local(tmp_path, monkeypatch):
    """networkx 分支删除知识节点 + 孤儿实体。"""
    import json as _json

    from app.services.graph_store import KnowledgeGraph

    graph_file = tmp_path / "kg.json"
    g = nx.DiGraph()
    g.add_node("1", type="knowledge", title="文档1")
    g.add_node("concept:A", type="concept", title="A")
    g.add_node("concept:B", type="concept", title="B")
    g.add_node("concept:C", type="concept", title="C")
    g.add_edge("1", "concept:A", relation="contains", weight=1.0)
    g.add_edge("1", "concept:B", relation="contains", weight=1.0)
    g.add_edge("1", "concept:C", relation="contains", weight=1.0)
    g.add_edge("concept:A", "concept:B", relation="related_to", weight=1.0)
    data = nx.node_link_data(g)
    graph_file.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")

    kg = KnowledgeGraph.__new__(KnowledgeGraph)
    kg.use_neo4j = False
    kg._neo4j_graph = None
    kg._nx_graph = g
    kg._synced_at = 0.0
    kg._sync_lock = threading.Lock()
    kg._nx_graph_file = graph_file

    ok = kg.remove_knowledge_node("1")
    assert ok
    # 文档节点删除；A/B 互连保留，C 只有 contains 边成孤儿被清
    assert not g.has_node("1")
    assert g.has_node("concept:A")
    assert g.has_node("concept:B")
    assert not g.has_node("concept:C")
