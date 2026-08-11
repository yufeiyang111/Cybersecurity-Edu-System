# -*- coding: utf-8 -*-
"""社区摘要服务测试：LLM 生成、缓存与签名失效、force、批量、单飞、解析容错。"""
import json
import threading

import networkx as nx
import pytest
from flask import Flask

from app import db
from app.models.knowledge_graph import KnowledgeGraphCommunitySummary
from app.services.kg.community_summarizer import CommunitySummarizer


@pytest.fixture
def db_app(tmp_path):
    """文件 sqlite app：跨线程共享同一数据库（:memory: 每线程独立连接会丢表）。"""
    import app.models  # noqa: F401  ensure all models registered for create_all

    class DbFileTestConfig:
        TESTING = True
        SECRET_KEY = "a" * 32
        JWT_SECRET_KEY = "b" * 32
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'kg_summaries.db'}"
        SQLALCHEMY_TRACK_MODIFICATIONS = False

    application = Flask(__name__)
    application.config.from_object(DbFileTestConfig)
    db.init_app(application)

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


SAMPLE_LLM_JSON = json.dumps({
    "title": "AD 域横向移动与票据攻击",
    "summary": "该社区聚焦域环境下的票据伪造与横向移动攻击链。",
    "key_topics": ["票据伪造", "NTLM 中继", "横向移动"],
    "representative_entities": [
        {"name": "Silver Ticket", "type": "attack_technique", "role": "伪造 TGS 票据"},
        {"name": "mimikatz", "type": "security_tool", "role": "票据导出工具"},
    ],
    "key_relationships": [
        {
            "source": "Silver Ticket",
            "relation": "uses",
            "target": "mimikatz",
            "description": "利用 mimikatz 生成并注入票据",
        },
    ],
    "security_implications": "域内票据可被伪造，应启用 Kerberos 加固。",
    "defensive_measures": ["启用金票保护", "监控异常 TGS 请求"],
}, ensure_ascii=False)


def _make_graph():
    g = nx.DiGraph()
    for i in range(1, 11):
        g.add_node(f"n{i}", type="concept", title=f"Node{i}")
    for i in range(1, 10):
        g.add_edge(f"n{i}", f"n{i + 1}", relation="related_to", weight=1.0)
    return g


def _make_summarizer(monkeypatch, llm_output=SAMPLE_LLM_JSON, call_count=None):
    summarizer = CommunitySummarizer()

    def fake_call(context):
        if call_count is not None:
            call_count.append(1)
        return llm_output

    monkeypatch.setattr(summarizer, "_call_llm", fake_call)
    return summarizer


def test_generate_persists_summary(app):
    summarizer = CommunitySummarizer()
    g = _make_graph()
    members = [f"n{i}" for i in range(1, 11)]

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(summarizer, "_call_llm", lambda ctx: SAMPLE_LLM_JSON)

    summary = summarizer.get_summary("0", members, g)
    monkeypatch.undo()

    assert summary is not None
    assert summary["_generated"] is True
    assert summary["title"] == "AD 域横向移动与票据攻击"
    assert summary["key_topics"] == ["票据伪造", "NTLM 中继", "横向移动"]
    assert len(summary["representative_entities"]) == 2
    assert len(summary["key_relationships"]) == 1
    assert summary["defensive_measures"]
    # 已落库
    row = KnowledgeGraphCommunitySummary.query.get("0")
    assert row is not None
    assert row.graph_signature == "10:9"


def test_cached_summary_reuses_llm_output(app, monkeypatch):
    calls = []
    summarizer = _make_summarizer(monkeypatch, call_count=calls)
    g = _make_graph()
    members = [f"n{i}" for i in range(1, 11)]

    first = summarizer.get_summary("0", members, g)
    second = summarizer.get_summary("0", members, g)

    assert first["title"] == second["title"]
    assert len(calls) == 1, "缓存命中不应再次调用 LLM"
    assert second["_generated"] is False


def test_summary_invalidated_when_graph_changes(app, monkeypatch):
    calls = []
    summarizer = _make_summarizer(monkeypatch, call_count=calls)
    g = _make_graph()
    members = [f"n{i}" for i in range(1, 11)]

    summarizer.get_summary("0", members, g)
    # 图谱变化（新增节点）：签名失效 → 重新生成
    g.add_node("n11", type="concept", title="Node11")
    summarizer.get_summary("0", members, g)

    assert len(calls) == 2, "图谱签名变化后应重新生成"
    row = KnowledgeGraphCommunitySummary.query.get("0")
    assert row.graph_signature == "11:9"


def test_force_regenerates(app, monkeypatch):
    calls = []
    summarizer = _make_summarizer(monkeypatch, call_count=calls)
    g = _make_graph()
    members = [f"n{i}" for i in range(1, 11)]

    summarizer.get_summary("0", members, g)
    summarizer.get_summary("0", members, g, force=True)

    assert len(calls) == 2, "force 应强制重新生成"


def test_llm_failure_returns_none(app, monkeypatch):
    summarizer = _make_summarizer(monkeypatch, llm_output=None)
    g = _make_graph()
    members = [f"n{i}" for i in range(1, 11)]

    summary = summarizer.get_summary("0", members, g)
    assert summary is None
    assert KnowledgeGraphCommunitySummary.query.get("0") is None


def test_parse_tolerates_fence_and_noise():
    raw = (
        "好的，以下是分析结果：\n"
        "```json\n"
        + SAMPLE_LLM_JSON + "\n"
        "```\n"
        "（完）"
    )
    parsed = CommunitySummarizer._parse_response(raw)
    assert parsed["title"] == "AD 域横向移动与票据攻击"
    assert parsed["key_topics"][0] == "票据伪造"


def test_parse_returns_none_for_invalid():
    assert CommunitySummarizer._parse_response("抱歉，我无法生成") is None
    assert CommunitySummarizer._parse_response("[1, 2, 3]") is None


def test_sample_context_builds_nodes_and_edges():
    g = _make_graph()
    members = [f"n{i}" for i in range(1, 11)]
    context = CommunitySummarizer()._sample_context(members, g)
    assert "Node1" in context
    assert "related_to" in context
    assert "社区代表节点" in context


def test_generate_batch_reports_status(db_app, monkeypatch):
    calls = []
    summarizer = _make_summarizer(monkeypatch, call_count=calls)
    g = _make_graph()
    communities = {
        "0": {"size": 10, "nodes": [f"n{i}" for i in range(1, 11)]},
        "1": {"size": 8, "nodes": [f"n{i}" for i in range(2, 10)]},
    }

    results = summarizer.generate_batch(communities, g, limit=2)
    assert len(results) == 2
    assert all(r["status"] == "generated" for r in results)
    assert {r["community_id"] for r in results} == {"0", "1"}
    assert all(r["title"] for r in results)
    assert len(calls) == 2


def test_generate_batch_failed_item_reported(db_app, monkeypatch):
    summarizer = CommunitySummarizer()

    def fake_call(context):
        if "Node1" in context:
            return None
        return SAMPLE_LLM_JSON

    monkeypatch.setattr(summarizer, "_call_llm", fake_call)
    g = _make_graph()
    communities = {
        "0": {"size": 10, "nodes": [f"n{i}" for i in range(1, 11)]},
        "1": {"size": 8, "nodes": [f"n{i}" for i in range(2, 10)]},
    }

    results = summarizer.generate_batch(communities, g, limit=2)
    statuses = {r["community_id"]: r["status"] for r in results}
    assert statuses["0"] == "failed"
    assert statuses["1"] == "generated"


def test_singleflight_concurrent_requests(db_app, monkeypatch):
    """并发请求同一社区只触发一次 LLM 调用。"""
    calls = []
    release = threading.Event()
    t2_started = threading.Event()

    summarizer = CommunitySummarizer()

    def fake_call(context):
        calls.append(1)
        release.wait(timeout=10)
        return SAMPLE_LLM_JSON

    monkeypatch.setattr(summarizer, "_call_llm", fake_call)
    g = _make_graph()
    members = [f"n{i}" for i in range(1, 11)]

    results = []
    errors = []

    def worker(t2):
        # 裸线程没有 Flask app context，手动包一层（db.session 需要）
        with db_app.app_context():
            if t2:
                t2_started.set()
            try:
                results.append(summarizer.get_summary("0", members, g))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

    t1 = threading.Thread(target=worker, args=(False,))
    t2 = threading.Thread(target=worker, args=(True,))
    t1.start()
    t2.start()
    # 等 t1 进入 LLM 调用（calls=1）且 t2 已开始执行，再留时间让 t2 走到
    # 单飞等待分支（此时 t1 仍阻塞在假 LLM 内，entry 必然存在），最后放行
    while len(calls) < 1 and t1.is_alive():
        release.wait(timeout=0.05)
    t2_started.wait(timeout=10)
    t2_started.clear()
    release.wait(timeout=0.3)
    release.set()
    t1.join(timeout=20)
    t2.join(timeout=20)

    assert not errors
    assert len(calls) == 1, "并发请求只应触发一次 LLM 调用"
    assert len(results) == 2
    assert all(r is not None and r["_generated"] is True for r in results)


def test_singleflight_failure_not_cascaded(db_app, monkeypatch):
    """生成失败时等待方直接拿到 None，不重复触发。"""
    calls = []
    release = threading.Event()
    t2_started = threading.Event()

    summarizer = CommunitySummarizer()

    def fake_call(context):
        calls.append(1)
        release.wait(timeout=10)
        return None

    monkeypatch.setattr(summarizer, "_call_llm", fake_call)
    g = _make_graph()
    members = [f"n{i}" for i in range(1, 11)]

    results = []

    def worker(t2):
        with db_app.app_context():
            if t2:
                t2_started.set()
            results.append(summarizer.get_summary("0", members, g))

    t1 = threading.Thread(target=worker, args=(False,))
    t2 = threading.Thread(target=worker, args=(True,))
    t1.start()
    t2.start()
    while len(calls) < 1 and t1.is_alive():
        release.wait(timeout=0.05)
    t2_started.wait(timeout=10)
    t2_started.clear()
    release.wait(timeout=0.3)
    release.set()
    t1.join(timeout=20)
    t2.join(timeout=20)

    assert len(calls) == 1
    assert all(r is None for r in results)


def test_get_cached_summary_only_reads(db_app, monkeypatch):
    calls = []
    summarizer = _make_summarizer(monkeypatch, call_count=calls)
    g = _make_graph()
    members = [f"n{i}" for i in range(1, 11)]

    assert summarizer.get_cached_summary("0", g) is None
    summarizer.get_summary("0", members, g)
    cached = summarizer.get_cached_summary("0", g)
    assert cached is not None
    assert cached["_generated"] is False
    assert len(calls) == 1, "只读查询不应触发 LLM"


