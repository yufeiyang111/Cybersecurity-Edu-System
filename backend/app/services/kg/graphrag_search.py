# -*- coding: utf-8 -*-
"""
GraphRAG 查询模式（Global Search / Local Search）

对齐 Microsoft GraphRAG 的两级查询：
- global_search(query)：回答"整个知识库/主题域在讲什么"类问题。
  对 Top N 大社区的 LLM 摘要做 Map-Reduce：先让 LLM 基于每个社区报告产出
  中间答案（含相关性判断），再把中间答案汇总为最终答案。
- local_search(query)：回答"特定实体/关系"类问题。
  图谱实体名匹配 query 关键词 → 邻居扩展（1-2 跳，含 description）→
  关联社区摘要 → LLM 综合生成带实体/关系/摘要来源的答案。

说明：
- 实体名匹配用 Neo4j 的 CONTAINS 模糊匹配（修复旧链路按 id 精确匹配
  get_neighbors(query) 不生效的问题）
- 社区摘要未生成的社区在 global_search 中跳过（可用批量预生成补齐）
- *stream 变体：SSE 流式输出最终答案（思考过程与答案增量实时推送），
  max_tokens 优先取用户偏好 qa_max_tokens，并写入 llm_call_logs 审计
"""
import json
import logging
import re
from typing import Any, Dict, Generator, List, Optional

from app.services.graph_communities import get_community_detector
from app.services.graph_store import get_knowledge_graph
from app.services.kg.community_summarizer import get_community_summarizer
from app.services.kg.llm_provider import get_llm_provider_client
from app.services.rag_prompt_builder import resolve_qa_max_tokens
from app.services.user_preferences import get_or_create as get_user_preferences

logger = logging.getLogger(__name__)

GLOBAL_SYSTEM_PROMPT = (
    "你是一名网络安全知识图谱分析师。用户会提出一个关于整个安全知识库的问题，"
    "同时给出若干社区报告的摘要（每个社区是一个主题相关的实体簇）。\n"
    "请针对**每一个社区报告**单独产出中间答案，格式为 JSON 数组：\n"
    '  [{"community_id": "社区编号", "relevant": true/false, "answer": "基于该社区的回答（1-3句）"}]\n'
    "要求：\n"
    "1. 只依据社区报告内容回答，禁止臆造报告中不存在的实体或事实；\n"
    "2. relevant 表示该社区与问题是否相关；不相关的社区 answer 可为空；\n"
    "3. 只输出 JSON 数组本身，不要输出解释或多余文字。"
)

GLOBAL_REDUCE_SYSTEM_PROMPT = (
    "你是一名网络安全知识图谱分析师。以下是针对同一问题的多个社区中间答案，"
    "请综合分析，产出一份完整的最终答案：\n"
    "1. 综合各社区的相关信息，组织成条理清晰的回答（先给出结论，再用 Markdown 分点展开，"
    "可使用 **加粗**、- 列表、1. 编号列表等 Markdown 结构）；\n"
    "2. 只使用中间答案提供的信息，禁止臆造；\n"
    "3. 若所有中间答案都不相关，直接说明知识库中没有与问题相关的内容。\n"
    "输出普通文本回答即可，无需 JSON。"
)

LOCAL_SYSTEM_PROMPT = (
    "你是一名网络安全知识图谱分析师。用户的问题与知识图谱中的特定实体相关。"
    "下面是图谱中匹配到的实体（含描述）、它们的关系，以及关联社区的摘要。\n"
    "请基于这些信息回答用户问题，要求：\n"
    "1. 先给出直接结论，再用 Markdown 分点展开（可使用 **加粗**、- 列表、"
    "1. 编号列表等结构），引用相关实体/关系/社区证据时在括号内标注实体名；\n"
    "2. 只使用给定信息，禁止臆造；信息不足时明确说明；\n"
    "3. 输出普通文本回答即可，无需 JSON。"
)


class GraphRagSearcher:
    """GraphRAG 全局/局部检索。"""

    def __init__(self) -> None:
        self._client = get_llm_provider_client()

    # ------------------------------------------------------------------
    # Global Search（社区摘要 Map-Reduce）
    # ------------------------------------------------------------------
    def global_search(
        self, query: str, top_k: int = 10,
    ) -> Dict[str, Any]:
        """全局检索：基于 Top N 大社区的摘要回答全局性问题。"""
        graph = get_knowledge_graph()
        graph_data = graph.graph
        detector = get_community_detector()
        detection = detector.detect(graph_data)
        communities = detection["communities"]

        # 取已有摘要的社区（按 size 降序 top_k），未生成摘要的跳过
        summarizer = get_community_summarizer()
        ordered = sorted(
            communities.items(), key=lambda kv: kv[1]["size"], reverse=True
        )
        used: List[Dict[str, Any]] = []
        for cid, info in ordered:
            if len(used) >= top_k:
                break
            summary = summarizer.get_cached_summary(cid, graph_data)
            if summary is None:
                continue
            used.append({
                "community_id": cid,
                "size": info["size"],
                "title": summary.get("title", ""),
                "summary": summary.get("summary", ""),
                "key_topics": summary.get("key_topics", []),
            })
        if not used:
            return {
                "answer": "知识库尚无社区摘要，无法进行全局检索。请先在图谱页生成社区摘要。",
                "used_communities": [],
                "intermediate": [],
                "mode": "global",
                "thinking": None,
                "provider": None,
                "model": None,
            }

        # Map：每个社区生成中间答案（一次 LLM 调用，带全部社区报告）
        intermediate = self._map_communities(query, used)
        # Reduce：汇总最终答案
        final_result = self._reduce_answers(query, intermediate)
        final_answer = final_result["text"]
        thinking = final_result["thinking"]
        return {
            "answer": final_answer,
            "used_communities": used,
            "intermediate": intermediate,
            "mode": "global",
            "thinking": thinking,
            "provider": final_result["provider"],
            "model": final_result["model"],
        }

    # ------------------------------------------------------------------
    # Local Search（实体匹配 + 邻居 + 社区摘要）
    # ------------------------------------------------------------------
    def local_search(
        self, query: str, max_depth: int = 2, top_entities: int = 8,
    ) -> Dict[str, Any]:
        """局部检索：围绕 query 匹配到的实体回答。"""
        graph = get_knowledge_graph()
        graph_data = graph.graph

        # 1. 实体匹配（Neo4j CONTAINS 模糊匹配；Neo4j 不可用时退化 networkx 名称匹配）
        matched = self._match_entities(query, top_entities)
        if not matched:
            matched = self._match_entities_networkx(graph_data, query, top_entities)
        if not matched:
            return {
                "answer": "图谱中没有找到与问题相关的实体，请换个问法或确认知识库内容。",
                "entities": [],
                "relationships": [],
                "community_summaries": [],
                "mode": "local",
                "thinking": None,
                "provider": None,
                "model": None,
            }

        # 2. 邻居扩展（1-2 跳，带 description 与关系）
        relationships = self._expand_neighbors(graph_data, matched, max_depth)

        # 3. 关联社区摘要（实体所属社区）
        community_summaries = self._community_summaries_for(matched)

        # 4. LLM 综合回答
        context = self._build_local_context(matched, relationships, community_summaries)
        result = self._client.call_with_thinking(
            context,
            system_prompt=LOCAL_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2048,
        )
        if result is None or not result.get("text"):
            answer = "LLM 生成失败，请稍后重试。"
            thinking = None
        else:
            answer = result["text"]
            thinking = result.get("thinking")
        return {
            "answer": answer,
            "entities": matched,
            "relationships": relationships,
            "community_summaries": community_summaries,
            "mode": "local",
            "thinking": thinking,
            "provider": result.get("provider") if result else None,
            "model": result.get("model") if result else None,
        }

    # ------------------------------------------------------------------
    # 流式变体（SSE：思考/答案增量 + done 载荷，审计 + 用户 max_tokens）
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_max_tokens(user_id: Optional[int]) -> int:
        """优先用户偏好的 qa_max_tokens（上下文窗口联动），否则系统默认。"""
        if not user_id:
            return resolve_qa_max_tokens(None)
        try:
            prefs = get_user_preferences(int(user_id))
            prefs_dict = prefs.to_dict() if hasattr(prefs, "to_dict") else {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取用户偏好失败 user=%s err=%s", user_id, type(exc).__name__)
            prefs_dict = {}
        return resolve_qa_max_tokens(prefs_dict)

    def global_search_stream(
        self, query: str, user_id: Optional[int] = None, top_k: int = 10,
    ) -> Generator[Dict[str, Any], None, None]:
        """全局检索流式版：Map 阶段取中间答案，Reduce 阶段 SSE 流式输出。"""
        graph = get_knowledge_graph()
        graph_data = graph.graph
        detector = get_community_detector()
        detection = detector.detect(graph_data)
        communities = detection["communities"]

        summarizer = get_community_summarizer()
        ordered = sorted(
            communities.items(), key=lambda kv: kv[1]["size"], reverse=True
        )
        used: List[Dict[str, Any]] = []
        for cid, info in ordered:
            if len(used) >= top_k:
                break
            summary = summarizer.get_cached_summary(cid, graph_data)
            if summary is None:
                continue
            used.append({
                "community_id": cid,
                "size": info["size"],
                "title": summary.get("title", ""),
                "summary": summary.get("summary", ""),
                "key_topics": summary.get("key_topics", []),
            })
        if not used:
            yield {
                "type": "done",
                "answer": "知识库尚无社区摘要，无法进行全局检索。请先在图谱页生成社区摘要。",
                "used_communities": [],
                "intermediate": [],
                "mode": "global",
                "usage": {},
                "provider": None,
                "model": None,
            }
            return

        intermediate = self._map_communities(query, used)
        max_tokens = self._resolve_max_tokens(user_id)
        blocks = [
            f"【社区 #{item['community_id']}】{item.get('title', '')}\n{item.get('answer', '')}"
            for item in intermediate
        ]
        user_content = f"用户问题：{query}\n\n中间答案：\n\n" + "\n\n".join(blocks)
        answer_parts: List[str] = []
        reasoning_parts: List[str] = []
        done_meta: Dict[str, Any] = {}
        for event in self._client.call_stream(
            user_content,
            system_prompt=GLOBAL_REDUCE_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=max_tokens,
            user_id=user_id,
            operation="graph_global_search",
        ):
            if event["type"] == "reasoning":
                reasoning_parts.append(event["text"])
                yield {"type": "reasoning", "text": event["text"]}
            elif event["type"] == "delta":
                answer_parts.append(event["text"])
                yield {"type": "delta", "text": event["text"]}
            elif event["type"] == "done":
                done_meta = event
            else:
                yield event
        if done_meta:
            yield {
                "type": "done",
                "answer": done_meta.get("text") or "".join(answer_parts),
                "thinking": done_meta.get("thinking") or "".join(reasoning_parts) or None,
                "used_communities": used,
                "intermediate": intermediate,
                "mode": "global",
                "usage": done_meta.get("usage") or {},
                "provider": done_meta.get("provider"),
                "model": done_meta.get("model"),
            }

    def local_search_stream(
        self, query: str, user_id: Optional[int] = None, max_depth: int = 2,
    ) -> Generator[Dict[str, Any], None, None]:
        """局部检索流式版：匹配实体/邻居/社区摘要后 SSE 流式输出回答。"""
        graph = get_knowledge_graph()
        graph_data = graph.graph

        matched = self._match_entities(query, 8)
        if not matched:
            matched = self._match_entities_networkx(graph_data, query, 8)
        if not matched:
            yield {
                "type": "done",
                "answer": "图谱中没有找到与问题相关的实体，请换个问法或确认知识库内容。",
                "entities": [],
                "relationships": [],
                "community_summaries": [],
                "mode": "local",
                "usage": {},
                "provider": None,
                "model": None,
            }
            return

        relationships = self._expand_neighbors(graph_data, matched, max_depth)
        community_summaries = self._community_summaries_for(matched)
        context = self._build_local_context(matched, relationships, community_summaries)
        max_tokens = self._resolve_max_tokens(user_id)

        answer_parts: List[str] = []
        reasoning_parts: List[str] = []
        done_meta: Dict[str, Any] = {}
        for event in self._client.call_stream(
            context,
            system_prompt=LOCAL_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=max_tokens,
            user_id=user_id,
            operation="graph_local_search",
        ):
            if event["type"] == "reasoning":
                reasoning_parts.append(event["text"])
                yield {"type": "reasoning", "text": event["text"]}
            elif event["type"] == "delta":
                answer_parts.append(event["text"])
                yield {"type": "delta", "text": event["text"]}
            elif event["type"] == "done":
                done_meta = event
            else:
                yield event
        if done_meta:
            yield {
                "type": "done",
                "answer": done_meta.get("text") or "".join(answer_parts),
                "thinking": done_meta.get("thinking") or "".join(reasoning_parts) or None,
                "entities": matched,
                "relationships": relationships,
                "community_summaries": community_summaries,
                "mode": "local",
                "usage": done_meta.get("usage") or {},
                "provider": done_meta.get("provider"),
                "model": done_meta.get("model"),
            }

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_intermediate(raw: str) -> List[Dict[str, Any]]:
        """解析 Map 阶段中间答案 JSON 数组（容错围栏/前后缀）。"""
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        text = text.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]")
            if start == -1 or end <= start:
                return []
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return []
        if not isinstance(parsed, list):
            return []
        return [
            item for item in parsed
            if isinstance(item, dict) and item.get("community_id") is not None
        ]

    def _map_communities(
        self, query: str, communities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Map 阶段：一次 LLM 调用产出每个社区的中间答案。"""
        blocks = []
        for c in communities:
            topics = "、".join(c.get("key_topics", []))
            blocks.append(
                f"【社区 #{c['community_id']}】{c.get('title', '')}\n"
                f"关键主题：{topics}\n"
                f"摘要：{c.get('summary', '')}"
            )
        user_content = (
            f"用户问题：{query}\n\n"
            f"社区报告（{len(communities)} 个）：\n\n"
            + "\n\n".join(blocks)
        )
        raw = self._client.call(
            user_content,
            system_prompt=GLOBAL_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=2048,
        )
        if not raw:
            return []
        parsed = self._parse_intermediate(raw)
        if not parsed:
            return []
        # 只保留 relevant 的中间答案，并过滤不存在的 community_id
        by_id = {str(c["community_id"]): c for c in communities}
        result = []
        for item in parsed:
            cid = str(item.get("community_id"))
            if cid not in by_id or not item.get("relevant"):
                continue
            result.append({
                "community_id": cid,
                "title": by_id[cid].get("title", ""),
                "answer": item.get("answer", ""),
            })
        return result

    def _reduce_answers(
        self, query: str, intermediate: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Reduce 阶段：汇总中间答案为最终答案（含思考过程与模型信息）。"""
        if not intermediate:
            return {
                "text": "未找到与问题相关的社区内容，知识库中可能没有该主题。",
                "thinking": None,
                "provider": None,
                "model": None,
            }
        blocks = [
            f"【社区 #{item['community_id']}】{item.get('title', '')}\n{item.get('answer', '')}"
            for item in intermediate
        ]
        user_content = f"用户问题：{query}\n\n中间答案：\n\n" + "\n\n".join(blocks)
        result = self._client.call_with_thinking(
            user_content,
            system_prompt=GLOBAL_REDUCE_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2048,
        )
        if result is None or not result.get("text"):
            return {
                "text": "LLM 生成失败，请稍后重试。",
                "thinking": None,
                "provider": None,
                "model": None,
            }
        return {
            "text": result["text"],
            "thinking": result.get("thinking"),
            "provider": result.get("provider"),
            "model": result.get("model"),
        }

    def _match_entities(self, query: str, top: int) -> List[Dict[str, Any]]:
        """Neo4j 实体名 CONTAINS 匹配（按 degree 降序）。"""
        graph = get_knowledge_graph()
        if not graph.use_neo4j or graph._neo4j_graph is None:
            return []
        keywords = self._query_keywords(query)
        if not keywords:
            return []
        try:
            with graph._neo4j_graph.driver.session() as session:
                result = session.run(
                    "MATCH (e:Entity) "
                    "WHERE ANY(k IN $keywords WHERE e.name CONTAINS k OR e.id CONTAINS k) "
                    "OPTIONAL MATCH (e)-[r]-() "
                    "WITH e, count(r) AS deg "
                    "RETURN e.id AS id, e.name AS name, e.type AS type, "
                    "e.description AS description, deg "
                    "ORDER BY deg DESC LIMIT $top",
                    {"keywords": keywords, "top": top},
                )
                return [
                    {
                        "id": record["id"],
                        "name": record["name"],
                        "type": record["type"] or "concept",
                        "description": record["description"] or "",
                        "degree": int(record["deg"]),
                    }
                    for record in result
                ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("图谱实体匹配失败: %s", type(exc).__name__)
            return []

    def _match_entities_networkx(
        self, graph_data, query: str, top: int,
    ) -> List[Dict[str, Any]]:
        """Neo4j 不可用时的 networkx 名称匹配兜底。"""
        keywords = self._query_keywords(query)
        if not keywords:
            return []
        matches = []
        for node_id, attrs in graph_data.nodes(data=True):
            title = attrs.get("title", "") or ""
            if attrs.get("type") in (None, "knowledge", "unknown"):
                continue
            if any(k and k in title for k in keywords) or any(
                k and k in node_id for k in keywords
            ):
                matches.append({
                    "id": node_id,
                    "name": title,
                    "type": attrs.get("type", "concept"),
                    "description": attrs.get("description", ""),
                    "degree": int(graph_data.degree(node_id)),
                })
        matches.sort(key=lambda m: m["degree"], reverse=True)
        return matches[:top]

    def _expand_neighbors(
        self, graph_data, entities: List[Dict[str, Any]], max_depth: int,
    ) -> List[Dict[str, Any]]:
        """在 networkx 视图中做 BFS 邻居扩展（限 depth 与数量）。"""
        entity_ids = {e["id"] for e in entities}
        seen: Dict[str, int] = {nid: 0 for nid in entity_ids}
        frontier = list(entity_ids)
        depth = 0
        while frontier and depth < max_depth:
            next_frontier = []
            for node_id in frontier:
                for neighbor in graph_data.neighbors(node_id):
                    if neighbor not in seen:
                        seen[neighbor] = depth + 1
                        next_frontier.append(neighbor)
                for predecessor in graph_data.predecessors(node_id):
                    if predecessor not in seen:
                        seen[predecessor] = depth + 1
                        next_frontier.append(predecessor)
            frontier = next_frontier
            depth += 1

        relationships: List[Dict[str, Any]] = []
        rel_seen: set = set()
        for u, v, attrs in graph_data.edges(data=True):
            if u not in seen or v not in seen:
                continue
            key = (u, v, attrs.get("relation", ""))
            if key in rel_seen:
                continue
            rel_seen.add(key)
            u_data = graph_data.nodes[u]
            v_data = graph_data.nodes[v]
            relationships.append({
                "source": u,
                "source_name": u_data.get("title") or u,
                "source_type": u_data.get("type", "unknown"),
                "relation": attrs.get("relation", "related_to"),
                "target": v,
                "target_name": v_data.get("title") or v,
                "target_type": v_data.get("type", "unknown"),
            })
        # 关系按与 seed 实体的关联优先，限量展示
        relationships.sort(
            key=lambda r: (r["source"] in entity_ids or r["target"] in entity_ids),
            reverse=True,
        )
        return relationships[:40]

    def _community_summaries_for(
        self, entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """实体所属社区的摘要（按社区大小排序，去重）。"""
        graph = get_knowledge_graph()
        graph_data = graph.graph
        detector = get_community_detector()
        detection = detector.detect(graph_data)
        node_community = detection["node_community"]
        communities = detection["communities"]

        entity_ids = {e["id"] for e in entities}
        cids: List[str] = []
        for nid in entity_ids:
            cid = node_community.get(nid)
            if cid is not None and cid not in cids:
                cids.append(cid)
        if not cids:
            return []
        cids.sort(key=lambda cid: communities.get(cid, {}).get("size", 0), reverse=True)

        summarizer = get_community_summarizer()
        result = []
        for cid in cids[:3]:
            summary = summarizer.get_cached_summary(cid, graph_data)
            if summary is None:
                continue
            result.append({
                "community_id": cid,
                "title": summary.get("title", ""),
                "summary": summary.get("summary", ""),
            })
        return result

    def _build_local_context(
        self, entities: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
        community_summaries: List[Dict[str, Any]],
    ) -> str:
        """组装 Local Search 的 LLM 上下文。"""
        lines = ["匹配到的实体："]
        for e in entities:
            desc = e.get("description") or "（暂无描述）"
            lines.append(f"- {e['name']} [{e['type']}]：{desc}")
        lines.append("\n实体间关系（邻居扩展）：")
        for r in relationships[:30]:
            lines.append(
                f"- {r['source_name']} --{r['relation']}--> {r['target_name']}"
            )
        if community_summaries:
            lines.append("\n关联社区摘要：")
            for c in community_summaries:
                lines.append(f"- 【{c['title']}】{c['summary']}")
        return "\n".join(lines)

    @staticmethod
    def _query_keywords(query: str) -> List[str]:
        """从问题中提取候选实体关键词（分词：去停用词 + 标点切分）。"""
        STOPWORDS = {
            "什么", "如何", "怎么", "为什么", "哪些", "请问", "介绍", "是", "的", "了",
            "吗", "呢", "我", "你", "它", "请", "一个", "一下", "有", "没有", "关于",
            "这个", "那个", "what", "how", "why", "which", "is", "are", "the", "a",
            "an", "to", "of", "and", "or", "in", "on", "for", "with", "do", "does",
        }
        tokens = re.split(r"[\s,，。；;、!！?？:：\"'()\[\]{}<>/\\|~`@#$%^&*_+=\-]+", query)
        keywords = []
        for tok in tokens:
            tok = tok.strip()
            if not tok or tok.lower() in STOPWORDS:
                continue
            if len(tok) < 2:
                continue
            keywords.append(tok)
        # 长词直接整词匹配；另对中文做 2-gram 切分提升召回（如"票据攻击"→"票据"）
        grams = []
        for kw in keywords:
            grams.append(kw)
            if len(kw) >= 4 and re.search(r"[\u4e00-\u9fff]", kw):
                for i in range(0, len(kw) - 1):
                    gram = kw[i : i + 2]
                    if len(gram) < 2 or gram.lower() in STOPWORDS or gram in grams:
                        continue
                    grams.append(gram)
        return grams[:12]


_searcher: Optional[GraphRagSearcher] = None


def get_graphrag_searcher() -> GraphRagSearcher:
    """获取 GraphRAG 检索器单例。"""
    global _searcher
    if _searcher is None:
        _searcher = GraphRagSearcher()
    return _searcher


__all__ = ["GraphRagSearcher", "get_graphrag_searcher"]
