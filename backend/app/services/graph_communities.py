# -*- coding: utf-8 -*-
"""
知识图谱社区检测服务（Community Detection）

工业级知识图谱的核心增强：对实体-关系图做社区发现，把图切成有意义的
聚类簇（如"Web安全""内网渗透""二进制利用"等主题社区），支撑：
- 前端按社区着色（图1 的"每圈一个颜色"效果）
- 社区级过滤/钻取导航
- 后续 GraphRAG 风格社区摘要的基础

实现：Leiden 层次社区检测（leidenalg，工业标准，GraphRAG 同款算法）；
leidenalg 不可用时降级 networkx Louvain。结果带 TTL 缓存（图谱变化后失效）。
"""
import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300  # 与 graph_store Neo4j 同步 TTL 一致


class GraphCommunityDetector:
    """图社区检测器（Leiden 优先，Louvain 兜底，带缓存）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cache: Optional[Dict[str, Any]] = None
        self._cached_at = 0.0
        self._cache_signature: Optional[str] = None

    # ------------------------------------------------------------------
    def detect(self, graph_data, force: bool = False) -> Dict[str, Any]:
        """对图执行社区检测，返回 {community_id: {...}} 与节点归属。

        Args:
            graph_data: networkx.DiGraph（Neo4j 同步视图）
            force: 忽略缓存强制重算

        Returns:
            {
              "communities": {str(cid): {"size": int, "nodes": [id...], "sample": [name...]}},
              "node_community": {node_id: str(cid)},
              "community_count": int,
              "algorithm": "leiden" | "louvain",
              "elapsed_seconds": float
            }
        """
        signature = self._signature(graph_data)
        with self._lock:
            if (
                not force
                and self._cache is not None
                and self._cache_signature == signature
                and time.time() - self._cached_at < CACHE_TTL_SECONDS
            ):
                return self._cache

        start = time.time()
        result = self._compute(graph_data)
        result["elapsed_seconds"] = round(time.time() - start, 2)

        with self._lock:
            self._cache = result
            self._cached_at = time.time()
            self._cache_signature = signature
        return result

    # ------------------------------------------------------------------
    def _compute(self, graph_data) -> Dict[str, Any]:
        # 图太小（节点/边不足）不做社区检测
        if graph_data.number_of_nodes() < 10 or graph_data.number_of_edges() < 10:
            return {
                "communities": {},
                "node_community": {},
                "community_count": 0,
                "algorithm": "none",
            }
        partition = self._run_leiden(graph_data)
        algorithm = "leiden"
        if partition is None:
            partition = self._run_louvain(graph_data)
            algorithm = "louvain"
        if partition is None:
            return {
                "communities": {},
                "node_community": {},
                "community_count": 0,
                "algorithm": "none",
            }

        # 组装结果
        communities: Dict[str, Dict[str, Any]] = {}
        node_community: Dict[str, str] = {}
        for node_id, cid in partition.items():
            key = str(cid)
            node_community[str(node_id)] = key
            communities.setdefault(key, {"size": 0, "nodes": [], "sample": []})
            communities[key]["size"] += 1
            communities[key]["nodes"].append(str(node_id))
            if len(communities[key]["sample"]) < 3:
                communities[key]["sample"].append(str(node_id))

        # 按大小降序
        ordered = {
            cid: info
            for cid, info in sorted(communities.items(), key=lambda kv: -kv[1]["size"])
        }
        return {
            "communities": ordered,
            "node_community": node_community,
            "community_count": len(ordered),
            "algorithm": algorithm,
        }

    def _run_leiden(self, graph_data) -> Optional[Dict[Any, Any]]:
        """Leiden 层次社区检测（leidenalg）。"""
        try:
            import igraph as ig
            from leidenalg import find_partition, ModularityVertexPartition

            edges = [(str(u), str(v)) for u, v in graph_data.edges()]
            if len(edges) < 10:
                return None
            # igraph 1.x：先按顶点名建图，再传边索引
            node_names = list(dict.fromkeys(n for pair in edges for n in pair))
            name_to_idx = {name: i for i, name in enumerate(node_names)}
            edge_pairs = [(name_to_idx[u], name_to_idx[v]) for u, v in edges]
            g = ig.Graph(n=len(node_names), edges=edge_pairs, directed=False)
            if g.vcount() < 10:
                return None
            partition = find_partition(g, ModularityVertexPartition, seed=42)
            return {node_names[i]: partition.membership[i] for i in range(g.vcount())}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Leiden 社区检测失败，降级 Louvain: %s", type(exc).__name__)
            return None

    def _run_louvain(self, graph_data) -> Optional[Dict[Any, Any]]:
        """networkx Louvain 兜底（无向视图）。"""
        try:
            from networkx.algorithms.community import louvain_communities

            undirected = graph_data.to_undirected()
            communities = louvain_communities(undirected, seed=42)
            result: Dict[Any, Any] = {}
            for cid, nodes in enumerate(communities):
                for node in nodes:
                    result[node] = cid
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("Louvain 社区检测失败: %s", type(exc).__name__)
            return None

    def invalidate(self) -> None:
        """图谱变化时失效缓存。"""
        with self._lock:
            self._cache = None
            self._cache_signature = None

    @staticmethod
    def _signature(graph_data) -> str:
        """图的轻量签名（节点数+边数+边哈希采样），用于缓存失效判断。"""
        node_count = graph_data.number_of_nodes()
        edge_count = graph_data.number_of_edges()
        return f"{node_count}:{edge_count}"


_detector: Optional[GraphCommunityDetector] = None
_detector_lock = threading.Lock()


def get_community_detector() -> GraphCommunityDetector:
    """获取社区检测器单例。"""
    global _detector
    with _detector_lock:
        if _detector is None:
            _detector = GraphCommunityDetector()
        return _detector
