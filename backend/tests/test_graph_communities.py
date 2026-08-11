# -*- coding: utf-8 -*-
"""图社区检测服务测试：Leiden 分区、缓存命中、Louvain 兜底、路由。"""
import networkx as nx
import pytest

from app.services.graph_communities import GraphCommunityDetector, get_community_detector


def _make_community_graph():
    """两个明显社区的小图（双簇 + 桥接边）。"""
    g = nx.DiGraph()
    # 社区 A: a1-a5 全连接
    for i in range(1, 6):
        g.add_node(f"a{i}", type="concept", title=f"A{i}")
    for i in range(1, 6):
        for j in range(i + 1, 6):
            g.add_edge(f"a{i}", f"a{j}", relation="related_to")
            g.add_edge(f"a{j}", f"a{i}", relation="related_to")
    # 社区 B: b1-b5 全连接
    for i in range(1, 6):
        g.add_node(f"b{i}", type="concept", title=f"B{i}")
    for i in range(1, 6):
        for j in range(i + 1, 6):
            g.add_edge(f"b{i}", f"b{j}", relation="related_to")
            g.add_edge(f"b{j}", f"b{i}", relation="related_to")
    # 桥接
    g.add_edge("a1", "b1", relation="related_to")
    return g


def test_detect_returns_two_communities():
    detector = GraphCommunityDetector()
    result = detector.detect(_make_community_graph())
    assert result["community_count"] == 2, "双簇图应检出 2 个社区"
    assert result["algorithm"] in ("leiden", "louvain")
    assert result["node_community"]
    # 每个社区大小 >= 5（不应把 a/b 混在一起）
    sizes = [info["size"] for info in result["communities"].values()]
    assert min(sizes) >= 5
    assert all("sample" in info for info in result["communities"].values())


def test_detect_cache_hit():
    detector = GraphCommunityDetector()
    g = _make_community_graph()
    first = detector.detect(g)
    second = detector.detect(g)
    assert first is second, "缓存命中应返回同一对象"
    # force 重算
    third = detector.detect(g, force=True)
    assert third["community_count"] == first["community_count"]


def test_detect_ignores_tiny_graph():
    g = nx.DiGraph()
    g.add_edge("x", "y", relation="related_to")
    result = GraphCommunityDetector().detect(g)
    assert result["community_count"] == 0


def test_louvain_fallback_when_leiden_missing(monkeypatch):
    detector = GraphCommunityDetector()
    monkeypatch.setattr(detector, "_run_leiden", lambda g: None)
    result = detector.detect(_make_community_graph())
    assert result["algorithm"] == "louvain"
    assert result["community_count"] == 2


def test_singleton():
    assert get_community_detector() is get_community_detector()
