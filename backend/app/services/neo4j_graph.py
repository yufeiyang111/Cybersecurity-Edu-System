"""
Neo4j 知识图谱服务
使用 Neo4j 图数据库存储和查询知识图谱
"""
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable, AuthError
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

from app.config import Config


@dataclass
class Neo4jConfig:
    """Neo4j 连接配置"""
    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "password"
    database: str = "neo4j"


class Neo4jKnowledgeGraph:
    """基于 Neo4j 的知识图谱服务"""

    RELATION_TYPES = {
        "is_a": "包含关系",
        "part_of": "组成关系",
        "uses": "使用关系",
        "caused_by": "因果关系",
        "related_to": "相关关系",
        "depends_on": "依赖关系",
        "contrasts_with": "对比关系",
        "located_at": "位于关系",
        "implements": "实现关系",
        "contains": "包含关系",
        # LLM 知识图谱本体关系（kg/ontology.py）
        "exploits": "利用（漏洞 → 攻击技术）",
        "mitigates": "缓解（防御措施 → 攻击技术）",
        "detects": "检测（工具 → 漏洞/攻击技术）",
        "prerequisite": "前置知识（概念 → 概念）",
        "belongs_to": "属于（实体 → 更宏观实体）",
        "causes": "导致（攻击技术 → 漏洞/后果）",
    }

    ENTITY_TYPES = [
        "concept",      # 概念
        "technique",    # 技术
        "tool",         # 工具
        "vulnerability", # 漏洞
        "event",        # 事件
        "knowledge"     # 知识条目
    ]

    def __init__(self, config: Neo4jConfig = None):
        """初始化 Neo4j 连接"""
        if not NEO4J_AVAILABLE:
            print("警告: neo4j 库未安装，请运行: pip install neo4j")
            self.driver = None
            return

        if config is None:
            config = Neo4jConfig(
                uri=Config.NEO4J_URI if hasattr(Config, 'NEO4J_URI') else "bolt://localhost:7687",
                username=Config.NEO4J_USERNAME if hasattr(Config, 'NEO4J_USERNAME') else "neo4j",
                password=Config.NEO4J_PASSWORD if hasattr(Config, 'NEO4J_PASSWORD') else "password",
                database=Config.NEO4J_DATABASE if hasattr(Config, 'NEO4J_DATABASE') else "neo4j"
            )

        try:
            self.driver = GraphDatabase.driver(
                config.uri,
                auth=(config.username, config.password)
            )
            # 测试连接
            self.driver.verify_connectivity()
            print(f"成功连接到 Neo4j: {config.uri}")
            self._init_constraints()
        except (ServiceUnavailable, AuthError) as e:
            print(f"Neo4j 连接失败: {e}")
            self.driver = None

    def _init_constraints(self):
        """初始化数据库约束和索引"""
        if self.driver is None:
            return

        with self.driver.session() as session:
            # 创建唯一性约束
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Knowledge) REQUIRE n.id IS UNIQUE"
            ]

            # 创建索引
            indexes = [
                "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.name)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.type)",
                "CREATE INDEX IF NOT EXISTS FOR (n:Knowledge) ON (n.title)"
            ]

            for cql in constraints + indexes:
                try:
                    session.run(cql)
                except Exception as e:
                    print(f"初始化约束/索引失败: {e}")

    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()

    def add_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: str,
        properties: Dict[str, Any] = None
    ) -> bool:
        """
        添加实体节点

        Args:
            entity_id: 实体唯一ID
            name: 实体名称
            entity_type: 实体类型 (concept/technique/tool/vulnerability/event/knowledge)
            properties: 其他属性

        Returns:
            是否成功
        """
        if self.driver is None:
            return False

        properties = properties or {}

        cql = """
        MERGE (e:Entity {id: $entity_id})
        SET e.name = $name,
            e.type = $entity_type,
            e.updated_at = timestamp()
        """

        # 添加动态属性
        for key, value in properties.items():
            if key not in ["id", "name", "type"]:
                cql += f", e.{key} = ${key}"

        params = {
            "entity_id": entity_id,
            "name": name,
            "entity_type": entity_type,
            **properties
        }

        try:
            with self.driver.session() as session:
                session.run(cql, params)
            return True
        except Exception as e:
            print(f"添加实体失败: {e}")
            return False

    def add_knowledge_node(
        self,
        knowledge_id: str,
        title: str,
        content: str = "",
        category: str = "",
        tags: List[str] = None,
        properties: Dict[str, Any] = None
    ) -> bool:
        """
        添加知识条目节点

        Args:
            knowledge_id: 知识ID
            title: 标题
            content: 内容摘要
            category: 分类
            tags: 标签列表
            properties: 其他属性

        Returns:
            是否成功
        """
        if self.driver is None:
            return False

        properties = properties or {}
        tags = tags or []

        cql = """
        MERGE (k:Knowledge {id: $knowledge_id})
        SET k.title = $title,
            k.content = $content,
            k.category = $category,
            k.tags = $tags,
            k.updated_at = timestamp()
        """

        params = {
            "knowledge_id": knowledge_id,
            "title": title,
            "content": content[:500] if content else "",  # 限制内容长度
            "category": category,
            "tags": tags,
            **properties
        }

        try:
            with self.driver.session() as session:
                session.run(cql, params)
            return True
        except Exception as e:
            print(f"添加知识节点失败: {e}")
            return False

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight: float = 1.0,
        properties: Dict[str, Any] = None
    ) -> bool:
        """
        添加关系边

        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
            relation_type: 关系类型
            weight: 权重
            properties: 其他属性

        Returns:
            是否成功
        """
        if self.driver is None:
            return False

        properties = properties or {}

        # 关系类型验证
        if relation_type not in self.RELATION_TYPES:
            print(f"警告: 未知关系类型 {relation_type}")
            relation_type = "related_to"

        cql = """
        MATCH (source {id: $source_id})
        MATCH (target {id: $target_id})
        MERGE (source)-[r:RELATES {type: $relation_type}]->(target)
        SET r.weight = $weight,
            r.updated_at = timestamp()
        """

        params = {
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "weight": weight,
            **properties
        }

        try:
            with self.driver.session() as session:
                session.run(cql, params)
            return True
        except Exception as e:
            print(f"添加关系失败: {e}")
            return False

    def get_neighbors(
        self,
        node_id: str,
        depth: int = 1,
        relation_type: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        获取邻居节点

        Args:
            node_id: 节点ID
            depth: 深度
            relation_type: 关系类型过滤
            limit: 返回数量限制

        Returns:
            邻居节点列表
        """
        if self.driver is None:
            return []

        if depth == 1:
            cql = """
            MATCH (n {id: $node_id})-[r]->(neighbor)
            """
            if relation_type:
                cql += "WHERE r.type = $relation_type "

            cql += """
            RETURN neighbor.id AS node_id,
                   neighbor.name AS name,
                   neighbor.type AS type,
                   r.type AS relation,
                   r.weight AS weight,
                   1 AS distance
            LIMIT $limit
            """
        else:
            cql = f"""
            MATCH path = (n {{id: $node_id}})-[*1..{depth}]-(neighbor)
            WHERE NOT n = neighbor
            WITH path, neighbor, length(path) AS pathLength
            ORDER BY pathLength
            LIMIT $limit
            RETURN neighbor.id AS node_id,
                   neighbor.name AS name,
                   neighbor.type AS type,
                   [r IN relationships(path) | r.type] AS relations,
                   pathLength AS distance,
                   [n IN nodes(path) | n.id][0..-1] AS path
            """

        params = {
            "node_id": node_id,
            "relation_type": relation_type,
            "limit": limit
        }

        try:
            with self.driver.session() as session:
                results = session.run(cql, params)
                return [dict(record) for record in results]
        except Exception as e:
            print(f"查询邻居失败: {e}")
            return []

    def merge_entities(self, source_id: str, target_id: str) -> Optional[int]:
        """
        合并实体：把 source 的所有关系迁移到 target 并删除 source

        Args:
            source_id: 被合并的源实体ID
            target_id: 保留的目标实体ID

        Returns:
            迁移的关系数，失败返回 None
        """
        if self.driver is None:
            return None

        moved = 0
        params = {"source_id": source_id, "target_id": target_id}
        # 出边重定向：source -[r]-> x 变为 target -[r]-> x（跳过指向 target 自身的边）
        out_cql = """
        MATCH (s {id: $source_id})
        MATCH (t {id: $target_id})
        MATCH (s)-[r:RELATES]->(x)
        WHERE x.id <> $target_id
        MERGE (t)-[nr:RELATES]->(x)
        SET nr.type = r.type, nr.weight = r.weight
        DELETE r
        """
        # 入边重定向：x -[r]-> source 变为 x -[r]-> target（跳过 source 自身的入边）
        in_cql = """
        MATCH (s {id: $source_id})
        MATCH (t {id: $target_id})
        MATCH (x)-[r:RELATES]->(s)
        WHERE x.id <> $target_id
        MERGE (x)-[nr:RELATES]->(t)
        SET nr.type = r.type, nr.weight = r.weight
        DELETE r
        """
        try:
            with self.driver.session() as session:
                summary = session.run(out_cql, params).consume()
                moved += summary.counters.relationships_deleted
                summary = session.run(in_cql, params).consume()
                moved += summary.counters.relationships_deleted
                # 删除源节点及其残留边（含 source-target 之间的边）
                session.run(
                    "MATCH (s {id: $source_id}) DETACH DELETE s",
                    {"source_id": source_id}
                ).consume()
            return moved
        except Exception as e:
            print(f"合并实体失败: {e}")
            return None

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 3
    ) -> List[List[str]]:
        """
        查找两点间的路径

        Args:
            source_id: 起点ID
            target_id: 终点ID
            max_hops: 最大跳数

        Returns:
            路径列表
        """
        if self.driver is None:
            return []

        cql = f"""
        MATCH path = (source {{id: $source_id}})-[*1..{max_hops}]-(target {{id: $target_id}})
        RETURN [n IN nodes(path) | n.id] AS path,
               [r IN relationships(path) | r.type] AS relations
        ORDER BY length(path)
        LIMIT 10
        """

        params = {"source_id": source_id, "target_id": target_id}

        try:
            with self.driver.session() as session:
                results = session.run(cql, params)
                return [record["path"] for record in results]
        except Exception as e:
            print(f"查找路径失败: {e}")
            return []

    def search_by_type(
        self,
        entity_type: str,
        keyword: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        按类型搜索实体

        Args:
            entity_type: 实体类型
            keyword: 关键词
            limit: 限制数量

        Returns:
            实体列表
        """
        if self.driver is None:
            return []

        if keyword:
            cql = """
            MATCH (e:Entity {type: $entity_type})
            WHERE e.name CONTAINS $keyword
            RETURN e.id AS id, e.name AS name, e.type AS type
            LIMIT $limit
            """
            params = {"entity_type": entity_type, "keyword": keyword, "limit": limit}
        else:
            cql = """
            MATCH (e:Entity {type: $entity_type})
            RETURN e.id AS id, e.name AS name, e.type AS type
            LIMIT $limit
            """
            params = {"entity_type": entity_type, "limit": limit}

        try:
            with self.driver.session() as session:
                results = session.run(cql, params)
                return [dict(record) for record in results]
        except Exception as e:
            print(f"类型搜索失败: {e}")
            return []

    def get_related_concepts(
        self,
        concept: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        获取相关概念

        Args:
            concept: 概念名称
            limit: 返回数量

        Returns:
            相关概念列表
        """
        if self.driver is None:
            return []

        cql = """
        MATCH (e:Entity)
        WHERE e.name CONTAINS $concept OR e.type = 'concept'
        RETURN e.id AS node_id,
               e.name AS title,
               e.type AS type,
               size((e)-->) AS out_degree,
               size((e)<--) AS in_degree
        ORDER BY out_degree + in_degree DESC
        LIMIT $limit
        """

        params = {"concept": concept, "limit": limit}

        try:
            with self.driver.session() as session:
                results = session.run(cql, params)
                return [dict(record) for record in results]
        except Exception as e:
            print(f"获取相关概念失败: {e}")
            return []

    def get_subgraph(
        self,
        node_ids: List[str],
        depth: int = 1
    ) -> Dict[str, Any]:
        """
        获取子图

        Args:
            node_ids: 节点ID列表
            depth: 扩展深度

        Returns:
            子图数据 {nodes: [], edges: []}
        """
        if self.driver is None:
            return {"nodes": [], "edges": []}

        cql = f"""
        MATCH path = (n)-[*1..{depth}]-(m)
        WHERE n.id IN $node_ids
        WITH collect(DISTINCT n) AS startNodes, collect(DISTINCT m) AS endNodes
        UNWIND (startNodes + endNodes) AS node
        WITH collect(DISTINCT node) AS allNodes
        UNWIND allNodes AS n
        OPTIONAL MATCH (n)-[r]-(m)
        RETURN DISTINCT n.id AS id, n.name AS name, n.type AS type,
               collect(DISTINCT r.type) AS relations
        """

        params = {"node_ids": node_ids}

        try:
            with self.driver.session() as session:
                results = session.run(cql, params)
                nodes = []
                edges = []

                for record in results:
                    if record["id"]:
                        nodes.append({
                            "id": record["id"],
                            "name": record["name"],
                            "type": record["type"]
                        })

                # 重新查询边
                edge_cql = f"""
                MATCH (n)-[r]->(m)
                WHERE n.id IN $node_ids
                RETURN DISTINCT n.id AS source, m.id AS target, r.type AS type, r.weight AS weight
                """
                edge_results = session.run(edge_cql, params)
                for record in edge_results:
                    edges.append({
                        "source": record["source"],
                        "target": record["target"],
                        "type": record["type"],
                        "weight": record.get("weight", 1.0)
                    })

                return {"nodes": nodes, "edges": edges}
        except Exception as e:
            print(f"获取子图失败: {e}")
            return {"nodes": [], "edges": []}

    def compute_pagerank(self, damping: float = 0.85, iterations: int = 20) -> Dict[str, float]:
        """
        计算 PageRank

        Args:
            damping: 阻尼系数
            iterations: 迭代次数

        Returns:
            节点ID到PageRank值的映射
        """
        if self.driver is None:
            return {}

        cql = """
        CALL gds.pageRank.write({
            nodeProjection: 'Entity',
            relationshipProjection: {
                RELATES: {type: 'RELATES', properties: 'weight'}
            },
            dampingFactor: $damping,
            maxIterations: $iterations,
            writeProperty: 'pagerank'
        })
        YIELD nodePropertiesWritten
        RETURN nodePropertiesWritten
        """

        params = {"damping": damping, "iterations": iterations}

        try:
            with self.driver.session() as session:
                session.run(cql, params)

                # 获取结果
                result_cql = """
                MATCH (e:Entity)
                WHERE e.pagerank IS NOT NULL
                RETURN e.id AS id, e.pagerank AS pagerank
                ORDER BY pagerank DESC
                """
                results = session.run(result_cql)
                return {record["id"]: record["pagerank"] for record in results}
        except Exception as e:
            print(f"计算PageRank失败 (可能 gds 插件未安装): {e}")
            # 备用：简单的基于度中心的计算
            return self._fallback_pagerank()

    def _fallback_pagerank(self) -> Dict[str, float]:
        """简单的基于度中心的排名（备用方案）"""
        if self.driver is None:
            return {}

        cql = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-->(e_out)
        OPTIONAL MATCH (e_in)-->(e)
        WITH e, count(DISTINCT e_out) AS out_degree, count(DISTINCT e_in) AS in_degree
        RETURN e.id AS id, (toFloat(out_degree) + toFloat(in_degree)) / 2.0 AS score
        ORDER BY score DESC
        """

        try:
            with self.driver.session() as session:
                results = session.run(cql)
                records = list(results)
                return {record["id"]: record["score"] for record in records}
        except Exception as e:
            print(f"备用PageRank计算失败: {e}")
            return {}

    def get_statistics(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        if self.driver is None:
            return {
                "node_count": 0,
                "edge_count": 0,
                "density": 0.0,
                "entity_types": {},
                "relation_types": {}
            }

        stats_cql = """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[r]->()
        RETURN count(DISTINCT e) AS node_count,
               count(DISTINCT r) AS edge_count
        """

        type_cql = """
        MATCH (e:Entity)
        RETURN e.type AS type, count(e) AS count
        """

        rel_cql = """
        MATCH ()-[r]->()
        RETURN r.type AS type, count(r) AS count
        """

        try:
            with self.driver.session() as session:
                # 节点和边统计
                stats_result = session.run(stats_cql)
                stats_record = stats_result.single()
                node_count = stats_record["node_count"] if stats_record else 0
                edge_count = stats_record["edge_count"] if stats_record else 0

                # 实体类型分布
                entity_types = {}
                type_result = session.run(type_cql)
                for record in type_result:
                    entity_types[record["type"] or "unknown"] = record["count"]

                # 关系类型分布
                relation_types = {}
                rel_result = session.run(rel_cql)
                for record in rel_result:
                    relation_types[record["type"] or "unknown"] = record["count"]

                # 计算密度
                density = 0.0
                if node_count > 1:
                    max_edges = node_count * (node_count - 1)
                    density = edge_count / max_edges if max_edges > 0 else 0.0

                return {
                    "node_count": node_count,
                    "edge_count": edge_count,
                    "density": density,
                    "entity_types": entity_types,
                    "relation_types": relation_types
                }
        except Exception as e:
            print(f"获取统计信息失败: {e}")
            return {}

    def delete_all(self) -> bool:
        """清空图谱"""
        if self.driver is None:
            return False

        cql = "MATCH (n) DETACH DELETE n"

        try:
            with self.driver.session() as session:
                session.run(cql)
            return True
        except Exception as e:
            print(f"清空图谱失败: {e}")
            return False


# 全局单例
neo4j_graph = None


def get_neo4j_graph() -> Neo4jKnowledgeGraph:
    """获取 Neo4j 知识图谱单例"""
    global neo4j_graph
    if neo4j_graph is None:
        neo4j_graph = Neo4jKnowledgeGraph()
    return neo4j_graph