# -*- coding: utf-8 -*-
"""
知识图谱构建编排（LLM 抽取式，工业级）

流程（标准四步法的落地实现）：
1. 内容分块：文档按段落/大小切成块（块内保留完整句子）
2. LLM 抽取：MiniMax 按本体从每块抽取"实体-关系-实体"三元组（JSON）
3. 实体消歧：embedding 相似度 + 同义词 + 编辑距离合并别名，得到全局共享实体
4. 存储入库：Neo4j（MERGE 幂等）——实体节点全局共享 id（type:canonical_name），
   知识条目节点 + contains 边关联，语义关系边直接入库

与旧正则实现（data_processor.build_knowledge_graph）的区别：
- 实体来自 LLM 语义理解而非硬编码正则词表
- 关系是语义关系（exploits/mitigates/detects/uses/prerequisite 等）而非共现启发式
- 实体节点全局共享（同名实体只有一个节点），跨文档关系天然成立
"""
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.graph_store import get_knowledge_graph
from app.services.kg.entity_resolution import resolve_triples
from app.services.kg.llm_extractor import LLMExtractor
from app.services.kg.ontology import ALL_RELATION_TYPES, ENTITY_TYPES
from app.services.secbert_embedding import get_embedding_service

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 24000  # LLM 抽取块上限（MiniMax-M2.7 上下文 128K，块内信息更全）


def _split_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """按段落/句子边界把文本切成 <= max_chars 的块。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    # 按双换行分段
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) > max_chars:
            # 超长段落按句子切
            sentences = re.split(r"(?<=[。！？.!?])\s*", para)
            for sent in sentences:
                if not sent.strip():
                    continue
                if len(current) + len(sent) + 1 > max_chars and current:
                    chunks.append(current)
                    current = ""
                current += sent
        else:
            if len(current) + len(para) + 1 > max_chars and current:
                chunks.append(current)
                current = ""
            current += ("\n\n" + para) if current else para
    if current:
        chunks.append(current)
    return [c.strip() for c in chunks if c.strip()]


class KnowledgeGraphLLMBuilder:
    """LLM 知识图谱构建器。"""

    def __init__(
        self,
        extractor: Optional[LLMExtractor] = None,
        graph: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
    ) -> None:
        self.extractor = extractor or LLMExtractor()
        self.graph = graph or get_knowledge_graph()
        self.embedding_service = embedding_service or get_embedding_service()

    def build(
        self,
        knowledge_items: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """构建图谱：返回量化报告（节点/边/三元组/抽取统计）。"""
        start = time.time()
        total = len(knowledge_items)

        # ---------- 1. 分块 ----------
        doc_chunks: List[Tuple[str, str, str]] = []  # (doc_id, title, chunk_text)
        for item in knowledge_items:
            doc_id = str(item["id"])
            title = item.get("title", "") or ""
            text = f"{title}。{item.get('content', '')}"
            for chunk in _split_text(text):
                doc_chunks.append((doc_id, title, chunk))

        # ---------- 2. LLM 抽取（分批并发，批内 6 路并发） ----------
        all_triples: List[Dict[str, Any]] = []
        extraction_stats = {"llm": 0, "regex": 0, "failed_chunks": 0}
        docs_done = 0
        last_doc_id = None
        BATCH_SIZE = 18
        for start_idx in range(0, len(doc_chunks), BATCH_SIZE):
            batch = doc_chunks[start_idx : start_idx + BATCH_SIZE]
            batch_texts = [chunk_text for _doc_id, _title, chunk_text in batch]
            batch_results = self.extractor.extract_batch(batch_texts)
            for (_doc_id, title, _chunk_text), triples in zip(batch, batch_results):
                for t in triples:
                    t["_doc_id"] = _doc_id
                    t["_doc_title"] = title
                    source = t.get("_source", "llm")
                    extraction_stats[source if source in extraction_stats else "regex"] += 1
                if not triples:
                    extraction_stats["failed_chunks"] += 1
                all_triples.extend(triples)
                # 进度按文档推进（同文档多块只算一次）
                if _doc_id != last_doc_id:
                    docs_done += 1
                    last_doc_id = _doc_id
                    if progress_callback is not None:
                        progress_callback(docs_done, total)

        # ---------- 3. 实体消歧 ----------
        cleaned, resolver = resolve_triples(all_triples, embedding_service=self.embedding_service)
        entity_map = resolver.entities()

        # ---------- 4. 入库（Neo4j MERGE 幂等） ----------
        graph = self.graph
        nodes_added = 0
        edges_added = 0
        # 知识节点 + contains 边
        for item in knowledge_items:
            doc_id = str(item["id"])
            graph.add_knowledge_node(
                knowledge_id=doc_id,
                title=item.get("title", ""),
                content=(item.get("content") or "")[:500],
                category=item.get("category_name") or item.get("category") or "",
                tags=item.get("tags", []),
            )
            nodes_added += 1

        # 实体节点（全局共享 id）与 contains 边
        for canon, info in entity_map.items():
            entity_id = f"{info['type']}:{canon}"
            graph.add_entity(
                entity_id=entity_id,
                name=canon,
                entity_type=info["type"],
                properties={"ref_count": info["count"]},
            )
            nodes_added += 1

        # contains：知识 → 实体（去重）
        contains_seen: set = set()
        for t in all_triples:
            doc_id = t.get("_doc_id")
            for side in ("source", "target"):
                name = (t.get(side) or "").strip()
                etype = t.get(f"{side}_type") or "concept"
                if not name or etype not in ENTITY_TYPES:
                    continue
                canon = resolver.canonical_name(name, etype)
                entity_id = f"{resolver.entity_type(canon)}:{canon}"
                key = (doc_id, entity_id)
                if key in contains_seen:
                    continue
                contains_seen.add(key)
                graph.add_relation(source_id=doc_id, target_id=entity_id, relation_type="contains")
                edges_added += 1

        # 语义关系边（实体 → 实体）
        relation_counts: Dict[str, int] = {}
        for t in cleaned:
            src_id = f"{t['source_type']}:{t['source']}"
            tgt_id = f"{t['target_type']}:{t['target']}"
            if src_id == tgt_id:
                continue
            relation = t["relation"] if t["relation"] in ALL_RELATION_TYPES else "related_to"
            graph.add_relation(source_id=src_id, target_id=tgt_id, relation_type=relation)
            relation_counts[relation] = relation_counts.get(relation, 0) + 1
            edges_added += 1

        elapsed = round(time.time() - start, 2)
        return {
            "nodes_added": nodes_added,
            "edges_added": edges_added,
            "entities": len(entity_map),
            "triples": len(cleaned),
            "raw_triples": len(all_triples),
            "documents_processed": total,
            "chunks_processed": len(doc_chunks),
            "extraction_stats": extraction_stats,
            "relation_counts": relation_counts,
            "elapsed_seconds": elapsed,
        }


def build_knowledge_graph_llm(
    items: List[Dict[str, Any]],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """便捷入口：用 LLM 构建知识图谱。"""
    return KnowledgeGraphLLMBuilder().build(items, progress_callback=progress_callback)
