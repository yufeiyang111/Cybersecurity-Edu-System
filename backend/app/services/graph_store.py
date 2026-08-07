"""
知识图谱服务 - 统一接口
优先使用 Neo4j，降级使用 NetworkX
"""
from typing import List, Dict, Any, Optional, Tuple

# 尝试导入 Neo4j
try:
    from app.services.neo4j_graph import Neo4jKnowledgeGraph, get_neo4j_graph, NEO4J_AVAILABLE
    HAS_NEO4J = NEO4J_AVAILABLE
except ImportError:
    HAS_NEO4J = False

# NetworkX 作为备用
import networkx as nx
import json
import os
import time
from app.config import Config, DATA_DIR


class KnowledgeGraph:
    """
    统一的知识图谱接口
    优先使用 Neo4j，不可用时降级到 NetworkX
    """

    RELATION_TYPES = {
        "is_a": "包含关系",
        "part_of": "组成关系",
        "uses": "使用关系",
        "caused_by": "因果关系",
        "related_to": "相关关系",
        "depends_on": "依赖关系",
        "contrasts_with": "对比关系"
    }

    def __init__(self):
        """初始化知识图谱"""
        self.use_neo4j = HAS_NEO4J
        self._neo4j_graph = None
        self._nx_graph = None
        self._synced_at = 0.0

        if self.use_neo4j:
            try:
                self._neo4j_graph = get_neo4j_graph()
                if self._neo4j_graph.driver is None:
                    self.use_neo4j = False
                    print("Neo4j 连接失败，降级到 NetworkX")
            except Exception:
                self.use_neo4j = False

        if not self.use_neo4j:
            self._init_networkx()

    @property
    def graph(self):
        """返回 NetworkX 图（用于可视化）"""
        if self.use_neo4j and self._neo4j_graph:
            # Neo4j 模式：将 Neo4j 数据同步到 NetworkX
            self._ensure_networkx_synced()
            return self._nx_graph
        return self._nx_graph

    def _ensure_networkx_synced(self):
        """确保 NetworkX 图与 Neo4j 数据同步（带 30 秒缓存，避免重复全量拉取）"""
        if self._nx_graph is None:
            self._init_networkx()
        if self._synced_at and time.time() - self._synced_at < 30:
            return
        # 从 Neo4j 拉取所有节点和边来构建 NetworkX 图
        try:
            self._nx_graph = nx.DiGraph()

            # 直接查询所有节点（Entity 和 Knowledge 标签）
            with self._neo4j_graph.driver.session() as session:
                # 查询所有 Entity 节点
                entity_result = session.run("MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.type AS type, e.source_item AS source_item")
                for record in entity_result:
                    self._nx_graph.add_node(
                        record["id"],
                        type=record.get("type") or "unknown",
                        title=record.get("name") or "",
                        source_item=record.get("source_item") or ""
                    )

                # 查询所有 Knowledge 节点
                knowledge_result = session.run("MATCH (k:Knowledge) RETURN k.id AS id, k.title AS title")
                for record in knowledge_result:
                    self._nx_graph.add_node(record["id"], type="knowledge", title=record.get("title") or "")

                # 查询所有关系边
                edges_result = session.run("MATCH (source)-[r]->(target) RETURN source.id AS source, target.id AS target, r.type AS relation, r.weight AS weight")
                for record in edges_result:
                    self._nx_graph.add_edge(
                        record["source"],
                        record["target"],
                        relation=record.get("relation") or "related_to",
                        weight=record.get("weight") or 1.0
                    )
            self._synced_at = time.time()
        except Exception as e:
            print(f"Neo4j 同步到 NetworkX 失败: {e}")
            import traceback
            traceback.print_exc()
            if self._nx_graph is None:
                self._nx_graph = nx.DiGraph()

    def _invalidate_sync(self):
        """图谱发生写入后失效缓存，下次访问重新同步"""
        self._synced_at = 0.0

    def _init_networkx(self):
        """初始化 NetworkX 作为备用"""
        self._nx_graph = nx.DiGraph()
        self._nx_graph_file = DATA_DIR / "knowledge_graph.json"
        self._load_nx_graph()

    def _load_nx_graph(self):
        """从文件加载 NetworkX 图谱"""
        if self._nx_graph_file.exists():
            try:
                with open(self._nx_graph_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._nx_graph = nx.node_link_graph(data)
            except Exception as e:
                print(f"加载图谱失败: {e}")
                self._nx_graph = nx.DiGraph()

    def _save_nx_graph(self):
        """保存 NetworkX 图谱到文件"""
        try:
            self._nx_graph_file.parent.mkdir(parents=True, exist_ok=True)
            data = nx.node_link_data(self._nx_graph)
            with open(self._nx_graph_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存图谱失败: {e}")

    # ========== Neo4j 实现转发 ==========

    def add_node(self, node_id: str, node_type: str, properties: Dict[str, Any]) -> bool:
        """添加节点"""
        if self.use_neo4j and self._neo4j_graph:
            # Neo4j 使用不同的接口
            ok = self._neo4j_graph.add_entity(
                entity_id=node_id,
                name=properties.get("name", node_id),
                entity_type=node_type,
                properties=properties
            )
            if ok:
                self._invalidate_sync()
            return ok
        else:
            # NetworkX 实现
            try:
                self._nx_graph.add_node(node_id, type=node_type, **properties)
                self._save_nx_graph()
                return True
            except Exception:
                return False

    def add_edge(self, source_id: str, target_id: str, relation_type: str, weight: float = 1.0) -> bool:
        """添加边"""
        if self.use_neo4j and self._neo4j_graph:
            ok = self._neo4j_graph.add_relation(
                source_id=source_id,
                target_id=target_id,
                relation_type=relation_type,
                weight=weight
            )
            if ok:
                self._invalidate_sync()
            return ok
        else:
            try:
                self._nx_graph.add_edge(source_id, target_id, relation=relation_type, weight=weight)
                self._save_nx_graph()
                return True
            except Exception:
                return False

    def add_relation(self, source_id: str, target_id: str, relation_type: str, weight: float = 1.0, properties: Dict[str, Any] = None) -> bool:
        """添加关系（add_edge 的别名）"""
        return self.add_edge(source_id, target_id, relation_type, weight)

    def add_knowledge_node(self, knowledge_id: str, title: str, content: str = "", category: str = "", tags: List[str] = None, properties: Dict[str, Any] = None) -> bool:
        """添加知识条目节点"""
        if self.use_neo4j and self._neo4j_graph:
            ok = self._neo4j_graph.add_knowledge_node(
                knowledge_id=knowledge_id,
                title=title,
                content=content,
                category=category,
                tags=tags,
                properties=properties
            )
            if ok:
                self._invalidate_sync()
            return ok
        else:
            try:
                self._nx_graph.add_node(knowledge_id, type="knowledge", title=title, category=category, tags=",".join(tags or []))
                self._save_nx_graph()
                return True
            except Exception:
                return False

    def add_entity(self, entity_id: str, name: str, entity_type: str, properties: Dict[str, Any] = None) -> bool:
        """添加实体节点"""
        if self.use_neo4j and self._neo4j_graph:
            ok = self._neo4j_graph.add_entity(
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                properties=properties
            )
            if ok:
                self._invalidate_sync()
            return ok
        else:
            try:
                self._nx_graph.add_node(entity_id, type=entity_type, title=name, **(properties or {}))
                self._save_nx_graph()
                return True
            except Exception:
                return False

    def add_entities_from_knowledge(self, knowledge_items: List[Dict]) -> int:
        """从知识条目构建图谱节点"""
        if self.use_neo4j and self._neo4j_graph:
            count = 0
            for item in knowledge_items:
                if self._neo4j_graph.add_knowledge_node(
                    knowledge_id=str(item["id"]),
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    category=item.get("category", ""),
                    tags=item.get("tags", [])
                ):
                    count += 1
            return count
        else:
            count = 0
            for item in knowledge_items:
                node_id = str(item["id"])
                if not self._nx_graph.has_node(node_id):
                    self.add_node(
                        node_id=node_id,
                        node_type="knowledge",
                        properties={
                            "title": item.get("title", ""),
                            "category": item.get("category", ""),
                            "tags": ",".join(item.get("tags", []))
                        }
                    )
                    count += 1
            return count

    def build_relations(self, relations: List[Dict]) -> int:
        """批量构建关系"""
        count = 0
        for rel in relations:
            if self.add_edge(
                source_id=str(rel["source_id"]),
                target_id=str(rel["target_id"]),
                relation_type=rel.get("relation_type", "related_to"),
                weight=rel.get("weight", 1.0)
            ):
                count += 1
        return count

    def get_neighbors(self, node_id: str, depth: int = 1, relation_type: str = None) -> List[Dict]:
        """获取邻居节点"""
        if self.use_neo4j and self._neo4j_graph:
            return self._neo4j_graph.get_neighbors(
                node_id=node_id,
                depth=depth,
                relation_type=relation_type
            )
        else:
            # NetworkX 实现
            neighbors = []
            try:
                if depth == 1:
                    for neighbor in self._nx_graph.neighbors(node_id):
                        edge_data = self._nx_graph.get_edge_data(node_id, neighbor)
                        neighbors.append({
                            "node_id": neighbor,
                            "relation": edge_data.get("relation", "") if edge_data else "",
                            "weight": edge_data.get("weight", 1.0) if edge_data else 1.0,
                            "distance": 1
                        })
                else:
                    paths = list(nx.single_source_shortest_path(self._nx_graph, node_id, cutoff=depth).items())
                    for target, path in paths:
                        if target != node_id and len(path) <= depth:
                            total_weight = 0
                            for i in range(len(path) - 1):
                                edge_data = self._nx_graph.get_edge_data(path[i], path[i + 1])
                                total_weight += edge_data.get("weight", 1.0) if edge_data else 0
                            neighbors.append({
                                "node_id": target,
                                "path": path,
                                "distance": len(path) - 1,
                                "weight": total_weight
                            })
            except Exception as e:
                print(f"获取邻居失败: {e}")

            return neighbors

    def find_paths(self, source_id: str, target_id: str, max_hops: int = 3) -> List[List[str]]:
        """查找两点间的路径"""
        if self.use_neo4j and self._neo4j_graph:
            return self._neo4j_graph.find_paths(
                source_id=source_id,
                target_id=target_id,
                max_hops=max_hops
            )
        else:
            try:
                if not self._nx_graph.has_node(source_id) or not self._nx_graph.has_node(target_id):
                    return []
                paths = list(nx.all_simple_paths(self._nx_graph, source_id, target_id, cutoff=max_hops))
                return paths
            except Exception:
                return []

    def get_related_concepts(self, concept: str, limit: int = 10) -> List[Dict]:
        """获取相关概念"""
        if self.use_neo4j and self._neo4j_graph:
            return self._neo4j_graph.get_related_concepts(
                concept=concept,
                limit=limit
            )
        else:
            related = []
            for node_id, data in self._nx_graph.nodes(data=True):
                if concept.lower() in str(data.get("title", "")).lower():
                    degree = self._nx_graph.degree(node_id)
                    related.append({
                        "node_id": node_id,
                        "title": data.get("title", ""),
                        "type": data.get("type", ""),
                        "degree": degree
                    })
            return sorted(related, key=lambda x: x["degree"], reverse=True)[:limit]

    def search_by_relation(self, relation_type: str) -> List[Tuple[str, str]]:
        """按关系类型搜索"""
        if self.use_neo4j and self._neo4j_graph:
            # Neo4j 实现可能需要调整
            return []
        else:
            results = []
            for u, v, data in self._nx_graph.edges(data=True):
                if data.get("relation") == relation_type:
                    results.append((u, v))
            return results

    def get_subgraph(self, node_ids: List[str]) -> nx.DiGraph:
        """获取子图"""
        if self.use_neo4j and self._neo4j_graph:
            return self._neo4j_graph.get_subgraph(node_ids=node_ids)
        else:
            return self._nx_graph.subgraph(node_ids).copy()

    def compute_pagerank(self, damping: float = 0.85) -> Dict[str, float]:
        """计算PageRank"""
        if self.use_neo4j and self._neo4j_graph:
            return self._neo4j_graph.compute_pagerank(damping=damping)
        else:
            return nx.pagerank(self._nx_graph, alpha=damping)

    def get_statistics(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        if self.use_neo4j and self._neo4j_graph:
            return self._neo4j_graph.get_statistics()
        else:
            relation_counts = {rel: 0 for rel in self.RELATION_TYPES.keys()}
            for _, _, data in self._nx_graph.edges(data=True):
                rel = data.get("relation")
                if rel in relation_counts:
                    relation_counts[rel] += 1
            return {
                "node_count": self._nx_graph.number_of_nodes(),
                "edge_count": self._nx_graph.number_of_edges(),
                "density": nx.density(self._nx_graph),
                "relation_types": relation_counts
            }

    def delete_all(self) -> bool:
        """清空图谱"""
        if self.use_neo4j and self._neo4j_graph:
            ok = self._neo4j_graph.delete_all()
            if ok:
                self._invalidate_sync()
            return ok
        else:
            self._nx_graph = nx.DiGraph()
            self._save_nx_graph()
            return True


# 全局单例
knowledge_graph = None

def get_knowledge_graph() -> KnowledgeGraph:
    global knowledge_graph
    if knowledge_graph is None:
        knowledge_graph = KnowledgeGraph()
    return knowledge_graph