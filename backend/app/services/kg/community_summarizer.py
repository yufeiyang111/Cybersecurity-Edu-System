# -*- coding: utf-8 -*-
"""
知识图谱社区摘要服务（GraphRAG 风格 Community Summary）

对社区检测（Leiden/Louvain）产出的每个社区，优先采样代表性节点与关系，
调用 LLM 生成结构化社区报告（标题/总结/关键主题/代表实体/关键关系/
安全启示/防御建议），持久化到 MySQL 缓存（带图谱签名失效校验）。

设计要点：
- 缓存：kg_community_summaries 表；图谱签名（节点数:边数）一致时直接复用，
  避免每次浏览重复消耗 LLM 额度
- 单飞（single-flight）：同一社区并发请求只触发一次 LLM 调用，其余等待同一结果
- Provider：MiniMax 主 + 备用（deepseek-v4-flash），额度耗尽自动切换，
  与 kg/llm_extractor.py 同一套 provider 机制
- 批量：Top N 社区并行生成（默认并发 3），单个失败不阻塞其余
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set

from flask import current_app

from app import db
from app.models.knowledge_graph import KnowledgeGraphCommunitySummary
from app.services.kg.llm_provider import LLMProviderClient

logger = logging.getLogger(__name__)

# 每个社区送入 LLM 的上下文上限（节点/关系太多会超上下文且稀释重点）
MAX_CONTEXT_NODES = 40
MAX_CONTEXT_EDGES = 60
BATCH_MAX_WORKERS = 3

SUMMARIZE_SYSTEM_PROMPT = (
    "你是一名网络安全知识图谱分析师。知识图谱由安全文档自动抽取的实体（漏洞/攻击技术/"
    "防御措施/安全工具/概念/法规标准/威胁行为体）和语义关系构成，社区是一组高度相关的实体簇。\n"
    "请基于给定的社区代表节点与关系，生成该社区的结构化摘要报告，要求：\n"
    "1. 只依据提供的节点与关系归纳，禁止臆造社区中不存在的实体或关系；\n"
    "2. title 用一句话概括社区主题（如「AD 域横向移动与票据攻击」）；\n"
    "3. summary 用 3-5 句说明该社区整体在讲什么、实体之间如何关联；\n"
    "4. key_topics 列 3-6 个关键主题词；\n"
    "5. representative_entities 选 5-10 个最有代表性的实体，说明其在社区中的作用；\n"
    "6. key_relationships 选 3-8 条最能代表社区结构的关系；\n"
    "7. security_implications 说明该社区相关的安全风险/启示（1-3 句）；\n"
    "8. defensive_measures 列 2-4 条针对性防御建议；\n"
    "9. 输出必须是合法的 JSON 对象，结构为：\n"
    '   {"title": "...", "summary": "...", "key_topics": ["..."], '
    '"representative_entities": [{"name": "...", "type": "...", "role": "..."}], '
    '"key_relationships": [{"source": "...", "relation": "...", "target": "...", "description": "..."}], '
    '"security_implications": "...", "defensive_measures": ["..."]}\n'
    "10. 只输出 JSON 对象本身，不要输出解释、markdown 代码块或多余文字。"
)


class CommunitySummaryError(RuntimeError):
    """社区摘要生成失败（LLM 不可用/解析失败等）。"""


class CommunitySummarizer:
    """社区摘要生成器（LLM + DB 缓存 + 单飞）。"""

    def __init__(self) -> None:
        self._inflight: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._client = LLMProviderClient(
            system_prompt=SUMMARIZE_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2048,
        )

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def get_cached_summary(
        self, community_id: str, graph_data,
    ) -> Optional[Dict[str, Any]]:
        """只读查询缓存摘要（不触发生成）；无缓存或签名失效返回 None。"""
        signature = self._graph_signature(graph_data)
        return self._load_cache(community_id, signature)

    def get_summary(
        self, community_id: str, members: List[str], graph_data,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """获取社区摘要：缓存命中直接返回；否则生成并持久化。

        Args:
            community_id: 社区 partition id
            members: 社区内节点 id 列表
            graph_data: networkx.DiGraph
            force: 忽略缓存强制重新生成

        Returns:
            摘要 dict（to_dict 结构），LLM 失败返回 None（由调用方决定降级）
        """
        signature = self._graph_signature(graph_data)
        cached = self._load_cache(community_id, signature)
        if cached is not None and not force:
            return cached

        return self._generate_singleflight(community_id, members, graph_data, signature, force)

    def generate_batch(
        self, communities: Dict[str, Dict[str, Any]], graph_data,
        limit: int = 10, force: bool = False,
    ) -> List[Dict[str, Any]]:
        """批量生成 Top N（按 size 降序）社区摘要，逐个报告状态。

        Returns:
            [{"community_id": str, "size": int, "status": "generated"|"cached"|"failed",
              "title": str|None, "error": str|None}]
        """
        ordered = sorted(
            communities.items(),
            key=lambda kv: kv[1]["size"],
            reverse=True,
        )[:limit]

        # 工作线程没有 Flask app context，需把当前 app 传入供 db.session 使用
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            app = None

        def _run(cid: str, info: Dict[str, Any]) -> Dict[str, Any]:
            if app is not None:
                with app.app_context():
                    return self._summarize_one(cid, info, graph_data, force)
            return self._summarize_one(cid, info, graph_data, force)

        results: List[Optional[Dict[str, Any]]] = [None] * len(ordered)
        with ThreadPoolExecutor(max_workers=BATCH_MAX_WORKERS) as pool:
            futures = {
                pool.submit(_run, cid, info): idx
                for idx, (cid, info) in enumerate(ordered)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("批量社区摘要任务异常: %s", type(exc).__name__)
                    results[idx] = {
                        "community_id": ordered[idx][0],
                        "size": ordered[idx][1]["size"],
                        "status": "failed",
                        "error": "生成任务异常",
                    }
        return [r for r in results if r is not None]

    # ------------------------------------------------------------------
    # 生成
    # ------------------------------------------------------------------
    def _summarize_one(
        self, cid: str, info: Dict[str, Any], graph_data, force: bool,
    ) -> Dict[str, Any]:
        """批量场景的单个社区摘要（带状态上报）。"""
        summary = self.get_summary(cid, info["nodes"], graph_data, force=force)
        if summary is None:
            return {
                "community_id": cid,
                "size": info["size"],
                "status": "failed",
                "error": "LLM 生成失败",
            }
        return {
            "community_id": cid,
            "size": info["size"],
            "status": "generated" if summary.get("_generated") else "cached",
            "title": summary.get("title"),
        }

    def _generate_singleflight(
        self, community_id: str, members: List[str], graph_data,
        signature: str, force: bool, _depth: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """单飞：同一社区并发只触发一次 LLM 调用。

        等待方复用进行中的结果；生成失败（result=None）时等待方也返回 None，
        不重复重试（避免并发雪崩）。_depth 防极端竞态下的递归。
        """
        with self._lock:
            entry = self._inflight.get(community_id)
        if entry is not None:
            # 已有生成进行中：等待结果，避免重复消耗 LLM
            entry["event"].wait(timeout=300)
            result = entry.get("result")
            if result is not None:
                return dict(result)
            # 生成失败或等待超时：返回 None（调用方决定降级），不再重复触发
            return None

        with self._lock:
            if community_id in self._inflight:
                if _depth >= 2:
                    return None
                return self._generate_singleflight(
                    community_id, members, graph_data, signature, force, _depth + 1
                )
            entry = {
                "event": threading.Event(),
                "result": None,
            }
            self._inflight[community_id] = entry

        try:
            result = self._generate(community_id, members, graph_data, signature, force)
            entry["result"] = result
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "社区摘要生成异常 community=%s err=%s", community_id, type(exc).__name__
            )
            result = None
        finally:
            entry["event"].set()
            with self._lock:
                self._inflight.pop(community_id, None)
        return result

    def _generate(
        self, community_id: str, members: List[str], graph_data,
        signature: str, force: bool,
    ) -> Optional[Dict[str, Any]]:
        """LLM 生成 + 解析 + 落库；LLM 失败返回 None。"""
        context = self._sample_context(members, graph_data)
        raw = self._call_llm(context)
        if not raw:
            logger.warning("社区摘要 LLM 调用无输出 community=%s", community_id)
            return None
        parsed = self._parse_response(raw)
        if parsed is None:
            logger.warning("社区摘要 LLM 输出解析失败 community=%s", community_id)
            return None

        summary = self._upsert(community_id, signature, parsed)
        return summary

    # ------------------------------------------------------------------
    # 上下文采样（GraphRAG 的优先采样近似：degree 排序取代表）
    # ------------------------------------------------------------------
    def _sample_context(
        self, members: List[str], graph_data,
        max_nodes: int = MAX_CONTEXT_NODES,
        max_edges: int = MAX_CONTEXT_EDGES,
    ) -> str:
        """组装 LLM 上下文：Top degree 节点 + 社区内部高权重关系。"""
        if not members:
            return "（社区为空）"
        member_set: Set[str] = set(members)

        # 节点：按 degree 降序取代表（含类型与标题）
        ranked = sorted(members, key=lambda nid: graph_data.degree(nid), reverse=True)
        top_nodes = ranked[:max_nodes]
        node_lines = []
        for node_id in top_nodes:
            data = graph_data.nodes.get(node_id, {})
            node_type = data.get("type", "unknown")
            title = data.get("title") or node_id
            node_lines.append(f"- [{node_type}] {title} (id: {node_id})")

        # 边：社区内部边按 weight 降序
        internal_edges = []
        for source, target, attrs in graph_data.edges(data=True):
            if source in member_set and target in member_set:
                internal_edges.append((source, target, attrs))
        internal_edges.sort(
            key=lambda item: float(item[2].get("weight", 1.0) or 1.0),
            reverse=True,
        )
        edge_lines = []
        for source, target, attrs in internal_edges[:max_edges]:
            s_title = graph_data.nodes.get(source, {}).get("title") or source
            t_title = graph_data.nodes.get(target, {}).get("title") or target
            edge_lines.append(
                f"- {s_title} --{attrs.get('relation', 'related_to')}--> {t_title}"
            )

        return (
            f"社区代表节点（{len(top_nodes)}/{len(members)}）：\n"
            + "\n".join(node_lines)
            + f"\n\n社区内部关系（{min(len(internal_edges), max_edges)}条）：\n"
            + "\n".join(edge_lines)
        )

    # ------------------------------------------------------------------
    # LLM 调用（共享 LLMProviderClient；_call_llm 保留为测试桩点）
    # ------------------------------------------------------------------
    def _call_llm(self, context: str) -> Optional[str]:
        """调用 LLM 生成摘要；全部额度耗尽抛 QuotaExhaustedError。"""
        return self._client.call(context)

    # ------------------------------------------------------------------
    # 解析与持久化
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_response(raw: str) -> Optional[Dict[str, Any]]:
        """解析 LLM JSON 输出并规整字段（容忍围栏/前后缀噪声）。"""
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        text = text.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end <= start:
                return None
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        if not isinstance(parsed, dict):
            return None

        def _as_list(value: Any) -> List[Any]:
            if isinstance(value, list):
                return value
            return []

        entities = []
        for item in _as_list(parsed.get("representative_entities")):
            if isinstance(item, dict) and item.get("name"):
                entities.append({
                    "name": str(item["name"]),
                    "type": str(item.get("type", "concept")),
                    "role": str(item.get("role", "")),
                })
        relationships = []
        for item in _as_list(parsed.get("key_relationships")):
            if isinstance(item, dict) and item.get("source") and item.get("target"):
                relationships.append({
                    "source": str(item["source"]),
                    "relation": str(item.get("relation", "related_to")),
                    "target": str(item["target"]),
                    "description": str(item.get("description", "")),
                })
        return {
            "title": str(parsed.get("title", "")).strip() or "未命名社区",
            "summary": str(parsed.get("summary", "")).strip(),
            "key_topics": [str(t) for t in _as_list(parsed.get("key_topics")) if str(t).strip()],
            "representative_entities": entities[:10],
            "key_relationships": relationships[:8],
            "security_implications": str(parsed.get("security_implications", "")).strip(),
            "defensive_measures": [
                str(m) for m in _as_list(parsed.get("defensive_measures")) if str(m).strip()
            ],
        }

    def _upsert(
        self, community_id: str, signature: str, parsed: Dict[str, Any],
    ) -> Dict[str, Any]:
        """写入缓存（同主键覆盖），返回带元信息的完整 dict。"""
        row = KnowledgeGraphCommunitySummary.query.get(community_id)
        if row is None:
            row = KnowledgeGraphCommunitySummary(community_id=community_id)
            db.session.add(row)
        row.graph_signature = signature
        row.algorithm = "leiden"
        row.title = parsed["title"]
        row.summary = parsed["summary"]
        row.summary_json = parsed
        db.session.commit()
        db.session.refresh(row)
        result = row.to_dict()
        result["_generated"] = True
        return result

    # ------------------------------------------------------------------
    # 缓存读取
    # ------------------------------------------------------------------
    def _load_cache(self, community_id: str, signature: str) -> Optional[Dict[str, Any]]:
        row = KnowledgeGraphCommunitySummary.query.get(community_id)
        if row is None or row.graph_signature != signature:
            return None
        result = row.to_dict()
        result["_generated"] = False
        return result

    @staticmethod
    def _graph_signature(graph_data) -> str:
        """与社区检测一致的图谱签名（节点数:边数）。"""
        return f"{graph_data.number_of_nodes()}:{graph_data.number_of_edges()}"


_summarizer: Optional[CommunitySummarizer] = None
_summarizer_lock = threading.Lock()


def get_community_summarizer() -> CommunitySummarizer:
    """获取社区摘要器单例。"""
    global _summarizer
    with _summarizer_lock:
        if _summarizer is None:
            _summarizer = CommunitySummarizer()
        return _summarizer
