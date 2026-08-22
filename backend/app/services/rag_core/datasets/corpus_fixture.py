# -*- coding: utf-8 -*-
"""可复现、可校验的公共知识库离线评测语料夹具。

仅依赖项目既有的 `SAMPLE_KNOWLEDGE_ITEMS`（已结构化落库的公共知识库样例）
与真实的 `text_chunker.chunk_text`，在加载时用真实分块复现每一篇文档的
chunk_id / start_line / end_line，作为 gold evidence 的唯一真实来源。

为保证测试确定性、避免加载 embedding tokenizer / 大模型，这里强制
`TextChunker` 走字符估算分支（与真实检索使用同一分块入口 `chunk_text`，
仅 token 计数策略不同；行号由字符偏移推导，确定且不依赖外部模型）。
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.sample_data import SAMPLE_KNOWLEDGE_ITEMS
from app.services.text_chunker import HybridChunker

# 使用独立的 chunker 实例并强制字符估算，避免测试期加载 tokenizer / 模型与网络，
# 同时不污染全局 `hybrid_chunker` 单例（否则会影响 test_text_chunker 等其它测试）。
_LOCAL_CHUNKER = HybridChunker()
_LOCAL_CHUNKER.sentence_chunker._tokenizer_failed = True


def _chunk_text_local(text: str, doc_id: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """复刻 `chunk_text(strategy="smart")` 的 id 命名，但使用本地隔离的 chunker。"""
    chunks = _LOCAL_CHUNKER.smart_chunk(text, doc_id, metadata)
    for index, chunk in enumerate(chunks):
        chunk["id"] = f"doc_{doc_id}_chunk_{index}"
    return chunks

# 公共知识库规范版本（与 citation_manifest.DEFAULT_PUBLIC_CORPUS_VERSION 对齐）。
CORPUS_VERSION = "knowledge_embeddings-v1"


def build_sample_corpus() -> Dict[str, Dict[str, Any]]:
    """用稳定 doc_id（kb-<序号>）构建可加载语料，序号与 SAMPLE_KNOWLEDGE_ITEMS 顺序一致。"""
    corpus: Dict[str, Dict[str, Any]] = {}
    for index, item in enumerate(SAMPLE_KNOWLEDGE_ITEMS, start=1):
        doc_id = f"kb-{index}"
        corpus[doc_id] = {
            "id": doc_id,
            "title": item["title"],
            "content": item["content"],
            "source": item.get("source", ""),
            "tags": list(item.get("tags", [])),
            "difficulty": item.get("difficulty", "medium"),
            "category_id": item.get("category_id"),
        }
    return corpus


def chunk_corpus(corpus: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """对每篇文档用真实 `chunk_text`（smart 策略）复现检索期 chunk 与行号。"""
    chunks: Dict[str, List[Dict[str, Any]]] = {}
    for doc_id, doc in corpus.items():
        text = f"{doc['title']}。{doc['content']}"
        metadata = {
            "title": doc["title"],
            "source": doc["source"],
            "difficulty": doc["difficulty"],
            "category_name": "",
        }
        chunks[doc_id] = _chunk_text_local(text, doc_id, metadata)
    return chunks


def locate_evidence(
    corpus: Dict[str, Dict[str, Any]],
    chunks: Dict[str, List[Dict[str, Any]]],
    document_id: str,
    must_contain: str,
) -> Dict[str, Any]:
    """在真实分块结果中定位 `must_contain` 片段所属 chunk，返回可溯源 gold evidence。

    若片段不存在于该文档任何 chunk，直接抛错——强制 gold evidence 必须来自
    真实语料，禁止编造。
    """
    if document_id not in corpus:
        raise ValueError(f"unknown document_id in corpus: {document_id!r}")
    doc = corpus[document_id]
    for chunk in chunks[document_id]:
        if must_contain in chunk["text"]:
            return {
                "document_id": document_id,
                "title": doc["title"],
                "chunk_id": chunk["id"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "corpus_version": CORPUS_VERSION,
                "role": "primary",
            }
    raise ValueError(
        f"must_contain fragment not found in corpus document "
        f"{document_id!r}: {must_contain!r}"
    )


__all__ = [
    "CORPUS_VERSION",
    "build_sample_corpus",
    "chunk_corpus",
    "locate_evidence",
]
