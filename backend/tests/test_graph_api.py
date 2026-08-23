# -*- coding: utf-8 -*-
"""知识图谱 API 测试：最短路径、实体归并、中心性着色。

conftest 的通用 fixture 会 stub 掉 app.routes.admin，本文件需要真实加载
admin 蓝图，因此自建 fixture：保留 app.routes 真实路径、仅 stub 其余路由模块，
并用 NetworkX 内存图谱替换 get_knowledge_graph，避免测试触碰 Neo4j 与 DATA_DIR。
"""
from __future__ import annotations

import sys
import threading
import types
from pathlib import Path

import networkx as nx
import pytest
from flask import Blueprint
from flask_jwt_extended import create_access_token

from app import create_app, db
from app.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[1]

STUBBED_ROUTE_MODULES = {
    "app.routes.auth": "auth_bp",
    "app.routes.auth_preferences": "auth_preferences_bp",
    "app.routes.oauth": "oauth_bp",
    "app.routes.knowledge": "knowledge_bp",
    "app.routes.qa": "qa_bp",
    "app.routes.llm_health": "llm_health_bp",
    "app.routes.llm": "llm_bp",
    "app.routes.policies": "policies_bp",
    "app.routes.memories": "memories_bp",
}


def install_route_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    routes_dir = BACKEND_ROOT / "app" / "routes"
    routes_package = types.ModuleType("app.routes")
    routes_package.__path__ = [str(routes_dir)]
    monkeypatch.setitem(sys.modules, "app.routes", routes_package)

    for module_name, blueprint_name in STUBBED_ROUTE_MODULES.items():
        module = types.ModuleType(module_name)
        setattr(module, blueprint_name, Blueprint(blueprint_name, module_name))
        if module_name == "app.routes.oauth":
            setattr(module, "init_oauth", lambda app: None)
        monkeypatch.setitem(sys.modules, module_name, module)

    # admin 不 stub，强制从磁盘重新导入真实模块
    monkeypatch.delitem(sys.modules, "app.routes.admin", raising=False)


@pytest.fixture
def graph_api_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from conftest import TestConfig

    install_route_stubs(monkeypatch)
    config = type(
        "GraphApiTestConfig",
        (TestConfig,),
        {
            "SECURITY_WORKSPACE_ROOT": str(tmp_path / "workspaces"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "LOG_FILE": str(tmp_path / "logs" / "test.log"),
            "RQ_ASYNC": False,
        },
    )
    application = create_app(config)
    with application.app_context():
        import app.models

        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def seed_graph(graph_data: nx.DiGraph) -> None:
    """样例图：a-b-d、a-c-d 两条通路，e 仅与 b 反向相连，f 孤立"""
    for node_id, node_type, title, category in [
        ("a", "concept", "节点A", "基础"),
        ("b", "concept", "节点B", "基础"),
        ("c", "technique", "节点C", "技术"),
        ("d", "vulnerability", "节点D", "漏洞"),
        ("e", "tool", "节点E", "工具"),
        ("f", "concept", "节点F", "基础"),
    ]:
        graph_data.add_node(node_id, type=node_type, title=title, category=category)
    graph_data.add_edge("a", "b", relation="uses", weight=1.0)
    graph_data.add_edge("b", "d", relation="caused_by", weight=1.0)
    graph_data.add_edge("a", "c", relation="uses", weight=1.0)
    graph_data.add_edge("c", "d", relation="caused_by", weight=1.0)
    graph_data.add_edge("e", "b", relation="related_to", weight=1.0)


@pytest.fixture
def graph_stub(graph_api_app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """构造 NetworkX 内存图谱替换真实服务（不触发 Neo4j 连接与真实数据目录写入）"""
    from app.services.graph_store import KnowledgeGraph

    graph = KnowledgeGraph.__new__(KnowledgeGraph)
    graph.use_neo4j = False
    graph._neo4j_graph = None
    graph._nx_graph = nx.DiGraph()
    graph._nx_graph_file = tmp_path / "knowledge_graph.json"
    graph._synced_at = 0.0
    graph._sync_lock = threading.Lock()
    seed_graph(graph._nx_graph)

    # create_app 已把真实 admin 模块装入 sys.modules，直接替换其服务引用
    admin_module = sys.modules["app.routes.admin"]
    monkeypatch.setattr(admin_module, "get_knowledge_graph", lambda: graph)
    return graph


def auth_headers(application, user_id, role="user"):
    with application.app_context():
        token = create_access_token(
            identity=str(user_id),
            additional_claims={"role": role},
        )
    return {"Authorization": f"Bearer {token}"}


def make_user(application, username, email):
    with application.app_context():
        user = User(username=username, email=email, password_hash="x")
        db.session.add(user)
        db.session.commit()
        return user.id


# ==================== 最短路径 ====================

def test_path_returns_shortest_path_with_node_details(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "path1", "path1@example.test")
    client = graph_api_app.test_client()
    headers = auth_headers(graph_api_app, user_id)

    response = client.get("/api/admin/graph/path?source=a&target=d", headers=headers)

    assert response.status_code == 200
    body = response.json
    assert body["distance"] == 2
    assert body["nodes"][0]["id"] == "a"
    assert body["nodes"][-1]["id"] == "d"
    assert len(body["edges"]) == 2
    for edge in body["edges"]:
        assert {"source", "target", "relation", "weight"} <= set(edge.keys())
    assert all("name" in node and "type" in node for node in body["nodes"])


def test_path_handles_reverse_edges(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "path2", "path2@example.test")
    client = graph_api_app.test_client()

    # e -> b 为反向边，仍应可达
    response = client.get(
        "/api/admin/graph/path?source=e&target=d",
        headers=auth_headers(graph_api_app, user_id),
    )
    assert response.status_code == 200
    assert response.json["nodes"][0]["id"] == "e"
    assert response.json["nodes"][-1]["id"] == "d"


def test_path_missing_params_returns_400(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "path3", "path3@example.test")
    client = graph_api_app.test_client()
    headers = auth_headers(graph_api_app, user_id)

    assert client.get("/api/admin/graph/path", headers=headers).status_code == 400
    assert client.get("/api/admin/graph/path?source=a", headers=headers).status_code == 400
    assert client.get("/api/admin/graph/path?target=d", headers=headers).status_code == 400


def test_path_unknown_node_returns_404(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "path4", "path4@example.test")
    client = graph_api_app.test_client()
    headers = auth_headers(graph_api_app, user_id)

    assert client.get("/api/admin/graph/path?source=ghost&target=d", headers=headers).status_code == 404
    assert client.get("/api/admin/graph/path?source=a&target=ghost", headers=headers).status_code == 404


def test_path_disconnected_returns_empty(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "path5", "path5@example.test")
    client = graph_api_app.test_client()

    response = client.get(
        "/api/admin/graph/path?source=a&target=f",
        headers=auth_headers(graph_api_app, user_id),
    )
    assert response.status_code == 200
    assert response.json["nodes"] == []
    assert response.json["edges"] == []
    assert response.json["distance"] == 0


def test_path_accessible_without_auth(graph_api_app, graph_stub):
    """图谱路径查询属于公开浏览功能，未登录也可访问。"""
    client = graph_api_app.test_client()
    response = client.get("/api/admin/graph/path?source=a&target=d")
    assert response.status_code == 200


# ==================== 实体归并 ====================

def test_merge_redirects_edges_and_deletes_source(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "merge1", "merge1@example.test")
    client = graph_api_app.test_client()
    headers = auth_headers(graph_api_app, user_id, role="admin")

    response = client.post(
        "/api/admin/graph/merge",
        json={"source_id": "a", "target_id": "d"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json
    assert body["moved_edges"] == 2

    graph_data = graph_stub._nx_graph
    assert not graph_data.has_node("a")
    assert graph_data.has_edge("d", "b")
    assert graph_data.has_edge("d", "c")
    assert graph_data.has_edge("b", "d")
    assert graph_data.has_edge("e", "b")


def test_merge_skips_self_edge_and_counts_removed_edge(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "merge2", "merge2@example.test")
    client = graph_api_app.test_client()

    response = client.post(
        "/api/admin/graph/merge",
        json={"source_id": "a", "target_id": "b"},
        headers=auth_headers(graph_api_app, user_id, role="admin"),
    )
    assert response.status_code == 200
    assert response.json["moved_edges"] == 2

    graph_data = graph_stub._nx_graph
    assert not graph_data.has_node("a")
    # a->b 被删除（不自环），a->c 迁移为 b->c
    assert graph_data.has_edge("b", "c")
    assert graph_data.has_edge("b", "d")
    assert not graph_data.has_edge("b", "b")


def test_merge_collapses_duplicate_neighbor_edges(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "merge3", "merge3@example.test")
    client = graph_api_app.test_client()

    graph_stub._nx_graph.add_edge("a", "d", relation="uses", weight=1.0)
    graph_stub._nx_graph.add_edge("b", "d", relation="caused_by", weight=1.0)
    response = client.post(
        "/api/admin/graph/merge",
        json={"source_id": "b", "target_id": "a"},
        headers=auth_headers(graph_api_app, user_id, role="admin"),
    )
    assert response.status_code == 200

    graph_data = graph_stub._nx_graph
    assert not graph_data.has_node("b")
    # a->d 只保留一条（不重复）
    assert graph_data.has_edge("a", "d")
    assert len(list(graph_data.out_edges("a"))) == 2


def test_merge_validation(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "merge4", "merge4@example.test")
    client = graph_api_app.test_client()
    headers = auth_headers(graph_api_app, user_id, role="admin")

    assert client.post("/api/admin/graph/merge", json={}, headers=headers).status_code == 400
    assert client.post(
        "/api/admin/graph/merge",
        json={"source_id": "a"},
        headers=headers,
    ).status_code == 400
    assert client.post(
        "/api/admin/graph/merge",
        json={"source_id": "a", "target_id": "a"},
        headers=headers,
    ).status_code == 400
    assert client.post(
        "/api/admin/graph/merge",
        json={"source_id": "ghost", "target_id": "d"},
        headers=headers,
    ).status_code == 404
    assert client.post(
        "/api/admin/graph/merge",
        json={"source_id": "a", "target_id": "ghost"},
        headers=headers,
    ).status_code == 404


def test_merge_denies_non_admin(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "merge5", "merge5@example.test")
    client = graph_api_app.test_client()

    response = client.post(
        "/api/admin/graph/merge",
        json={"source_id": "a", "target_id": "b"},
        headers=auth_headers(graph_api_app, user_id, role="user"),
    )
    assert response.status_code == 403
    assert graph_stub._nx_graph.has_node("a")


def test_deduplicate_merges_same_name_entities(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "dedup1", "dedup1@example.test")
    client = graph_api_app.test_client()

    # 添加两组同名实体
    graph_stub._nx_graph.add_node("9_签名", type="concept", title="签名", category="")
    graph_stub._nx_graph.add_node("11_签名", type="concept", title="签名", category="")
    graph_stub._nx_graph.add_node("9_防火墙", type="concept", title="防火墙", category="")
    graph_stub._nx_graph.add_node("13_防火墙", type="concept", title="防火墙", category="")
    graph_stub._nx_graph.add_edge("9_签名", "b", relation="related_to", weight=1.0)
    graph_stub._nx_graph.add_edge("11_签名", "d", relation="related_to", weight=1.0)
    graph_stub._nx_graph.add_edge("9_防火墙", "e", relation="related_to", weight=1.0)
    graph_stub._nx_graph.add_edge("13_防火墙", "d", relation="related_to", weight=1.0)

    response = client.post(
        "/api/admin/graph/deduplicate",
        headers=auth_headers(graph_api_app, user_id, role="admin"),
    )
    assert response.status_code == 200
    body = response.json
    assert body["groups"] == 2
    assert body["removed_nodes"] == 2

    graph_data = graph_stub._nx_graph
    sign_nodes = [
        node_id for node_id, data in graph_data.nodes(data=True)
        if data.get("title") == "签名"
    ]
    assert len(sign_nodes) == 1
    assert graph_data.has_node("a") and graph_data.has_node("b")
    assert graph_data.has_edge(sign_nodes[0], "b") or graph_data.has_edge(sign_nodes[0], "d")


def test_deduplicate_requires_admin(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "dedup2", "dedup2@example.test")
    client = graph_api_app.test_client()

    response = client.post(
        "/api/admin/graph/deduplicate",
        headers=auth_headers(graph_api_app, user_id, role="user"),
    )
    assert response.status_code == 403


def test_related_returns_entity_source_items(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "src1", "src1@example.test")
    client = graph_api_app.test_client()

    # 给实体节点挂上多个来源知识条目（contains 入边，模拟归并后的形态）
    graph_stub._nx_graph.add_node("2", type="knowledge", title="加密技术", category="加密")
    graph_stub._nx_graph.add_node("3", type="knowledge", title="数字签名", category="加密")
    graph_stub._nx_graph.add_node("1_签名", type="concept", title="签名", category="")
    graph_stub._nx_graph.add_edge("2", "1_签名", relation="contains", weight=1.0)
    graph_stub._nx_graph.add_edge("3", "1_签名", relation="contains", weight=1.0)

    response = client.get(
        "/api/admin/graph/related/1_签名",
        headers=auth_headers(graph_api_app, user_id),
    )
    assert response.status_code == 200
    body = response.json
    source_ids = {source["id"] for source in body["sources"]}
    assert source_ids == {"2", "3"}
    titles = {source["title"] for source in body["sources"]}
    assert titles == {"加密技术", "数字签名"}


def test_related_returns_empty_sources_for_knowledge_node(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "src2", "src2@example.test")
    client = graph_api_app.test_client()

    graph_stub._nx_graph.add_node("2", type="knowledge", title="加密技术", category="加密")
    response = client.get(
        "/api/admin/graph/related/2",
        headers=auth_headers(graph_api_app, user_id),
    )
    assert response.status_code == 200
    assert response.json["sources"] == []


# ==================== 中心性 ====================

def test_centrality_pagerank_covers_all_nodes(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "cent1", "cent1@example.test")
    client = graph_api_app.test_client()

    response = client.get(
        "/api/admin/graph/centrality?metric=pagerank",
        headers=auth_headers(graph_api_app, user_id),
    )
    assert response.status_code == 200
    body = response.json
    assert body["metric"] == "pagerank"
    assert set(body["scores"].keys()) == {"a", "b", "c", "d", "e", "f"}
    for score in body["scores"].values():
        assert 0.0 <= score <= 1.0


def test_centrality_degree_counts_incident_edges(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "cent2", "cent2@example.test")
    client = graph_api_app.test_client()

    response = client.get(
        "/api/admin/graph/centrality?metric=degree",
        headers=auth_headers(graph_api_app, user_id),
    )
    assert response.status_code == 200
    scores = response.json["scores"]
    assert scores["a"] == 2  # a->b, a->c
    assert scores["b"] == 3  # a->b, e->b, b->d
    assert scores["f"] == 0  # 孤立节点
    assert scores["e"] == 1


def test_centrality_defaults_to_pagerank(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "cent3", "cent3@example.test")
    client = graph_api_app.test_client()

    response = client.get(
        "/api/admin/graph/centrality",
        headers=auth_headers(graph_api_app, user_id),
    )
    assert response.status_code == 200
    assert response.json["metric"] == "pagerank"


def test_centrality_invalid_metric_returns_400(graph_api_app, graph_stub):
    user_id = make_user(graph_api_app, "cent4", "cent4@example.test")
    client = graph_api_app.test_client()

    response = client.get(
        "/api/admin/graph/centrality?metric=betweenness",
        headers=auth_headers(graph_api_app, user_id),
    )
    assert response.status_code == 400


def test_centrality_accessible_without_auth(graph_api_app, graph_stub):
    """图谱中心性指标查询属于公开浏览功能，未登录也可访问。"""
    client = graph_api_app.test_client()
    assert client.get("/api/admin/graph/centrality").status_code == 200


# ==================== 跨条目同名实体关联（build_knowledge_graph） ====================

def test_build_knowledge_graph_links_same_name_entities_across_items():
    from app.services.data_processor import KnowledgeGraphBuilder

    graph_data = nx.DiGraph()

    def stub_add_relation(self, source_id, target_id, relation_type, weight=1.0, properties=None):
        graph_data.add_edge(source_id, target_id, relation=relation_type, weight=weight)
        return True

    builder = KnowledgeGraphBuilder()
    builder.knowledge_graph = type(
        "StubGraph",
        (),
        {
            "add_knowledge_node": lambda self, **kw: True,
            "add_entity": lambda self, **kw: True,
            "add_relation": stub_add_relation,
        },
    )()

    items = [
        {"id": 1, "title": "网络基础", "content": "TCP 协议与防火墙相关概念介绍", "category": "网络"},
        {"id": 2, "title": "加密技术", "content": "TCP 与加密技术的结合应用", "category": "加密"},
    ]
    result = builder.build_knowledge_graph(items)

    assert result["cross_item_edges"] >= 1
    assert graph_data.has_edge("1_TCP", "2_TCP")
    assert graph_data.get_edge_data("1_TCP", "2_TCP")["relation"] == "related_to"


def test_build_knowledge_graph_without_duplicate_entities_no_cross_edges():
    from app.services.data_processor import KnowledgeGraphBuilder

    graph_data = nx.DiGraph()

    def stub_add_relation(self, source_id, target_id, relation_type, weight=1.0, properties=None):
        graph_data.add_edge(source_id, target_id, relation=relation_type, weight=weight)
        return True

    builder = KnowledgeGraphBuilder()
    builder.knowledge_graph = type(
        "StubGraph",
        (),
        {
            "add_knowledge_node": lambda self, **kw: True,
            "add_entity": lambda self, **kw: True,
            "add_relation": stub_add_relation,
        },
    )()

    items = [
        {"id": 1, "title": "网络基础", "content": "TCP 协议介绍", "category": "网络"},
        {"id": 2, "title": "漏洞挖掘", "content": "缓冲区溢出与格式化字符串攻击", "category": "漏洞"},
    ]
    result = builder.build_knowledge_graph(items)

    # 两个条目无同名实体，不应产生跨条目边
    assert result["cross_item_edges"] == 0
