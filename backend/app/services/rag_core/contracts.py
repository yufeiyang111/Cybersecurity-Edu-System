# -*- coding: utf-8 -*-
"""企业级 RAG 管道跨阶段的不可变数据契约。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

AnswerStatus = Literal[
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "degraded",
]
RetrievalPath = Literal[
    "dense_only",
    "bm25_only",
    "both",
    "lexical_only_degraded",
    "legacy",
    "unknown",
]

_VALID_ANSWER_STATUSES = {
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "degraded",
}


@dataclass(frozen=True)
class RagExecutionRequest:
    """一次问答执行的输入；仅在内存中传递，不作为 trace 原文保存。"""

    query: str
    request_id: str | None = None
    conversation_history: tuple[Mapping[str, Any], ...] = ()
    use_rerank: bool = True
    user_preferences: Mapping[str, Any] | None = None
    user_id: int | None = None
    memories: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("RAG query must be a non-empty string")


@dataclass(frozen=True)
class Candidate:
    """候选块在检索、重排和 Evidence Pack 阶段之间传递的统一结构。"""

    document_id: str
    title: str
    source: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    chunk_id: str | None = None
    corpus_version: str | None = None
    title_path: str | None = None
    content: str = field(default="", repr=False, compare=False)
    parent_content: str | None = field(default=None, repr=False, compare=False)
    dense_score: float | None = None
    dense_rank: int | None = None
    bm25_score: float | None = None
    bm25_rank: int | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    rank: int | None = None
    retrieval_path: RetrievalPath = "unknown"
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def trace_summary(self) -> dict[str, Any]:
        """返回可落库的候选摘要，绝不携带正文或 parent_text。"""
        return {
            "document_id": self.document_id,
            "dense_score": self.dense_score,
            "dense_rank": self.dense_rank,
            "bm25_score": self.bm25_score,
            "bm25_rank": self.bm25_rank,
            "rrf_score": self.rrf_score,
            "rerank_score": self.rerank_score,
            "rank": self.rank,
            "retrieval_path": self.retrieval_path,
        }


@dataclass(frozen=True)
class EvidenceReference:
    """一个可定位、可展示的证据引用；正文仅用于模型上下文，不进入 manifest。"""

    citation_id: str
    document_id: str
    title: str
    source: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    chunk_id: str | None = None
    corpus_version: str | None = None
    title_path: str | None = None
    content: str = field(default="", repr=False, compare=False)

    def to_manifest_dict(self) -> dict[str, Any]:
        """生成可以返回给前端或落库的引用信息，不含证据正文。"""
        return {
            "citation_id": self.citation_id,
            "document_id": self.document_id,
            "title": self.title,
            "source": self.source,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "chunk_id": self.chunk_id,
            "corpus_version": self.corpus_version,
            "title_path": self.title_path,
        }


@dataclass(frozen=True)
class EvidencePack:
    """受 token 预算约束的最终证据集合。"""

    references: tuple[EvidenceReference, ...]
    token_count: int
    token_budget: int

    def __post_init__(self) -> None:
        if self.token_count < 0:
            raise ValueError("Evidence token_count cannot be negative")
        if self.token_budget <= 0:
            raise ValueError("Evidence token_budget must be positive")
        if self.token_count > self.token_budget:
            raise ValueError("Evidence token_count cannot exceed token_budget")


@dataclass(frozen=True)
class CitationManifest:
    """答案 claim 到稳定 citation ID 的映射，不能由模型随意指向库外资料。"""

    references: tuple[EvidenceReference, ...]
    claim_citations: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """返回不含文档正文的 JSON 安全结构。"""
        return {
            "citations": [reference.to_manifest_dict() for reference in self.references],
            "claim_citations": {
                claim: list(citation_ids)
                for claim, citation_ids in self.claim_citations.items()
            },
        }


@dataclass(frozen=True)
class RetrievalTrace:
    """可观测性 trace；只记录摘要、指纹和阶段计数，禁止记录 query/Prompt/CoT。"""

    request_id: str | None
    query_fingerprint: str
    pipeline_version_key: str
    stage_summary: Mapping[str, Any]
    warnings: tuple[str, ...] = ()
    retrieval_ms: int = 0
    trace_id: int | None = None

    def to_storage_dict(self) -> dict[str, Any]:
        """返回持久化用脱敏摘要。"""
        return {
            "request_id": self.request_id,
            "query_fingerprint": self.query_fingerprint,
            "pipeline_version_key": self.pipeline_version_key,
            "stage_summary": dict(self.stage_summary),
            "warnings": list(self.warnings),
            "retrieval_ms": self.retrieval_ms,
        }


@dataclass(frozen=True)
class RagExecutionResult:
    """企业 RAG 管道的统一输出；provider reasoning 仅用于当前 QA 归属记录展示。"""

    answer: str
    answer_status: AnswerStatus
    citations: CitationManifest
    trace: RetrievalTrace
    confidence: float | None = None
    model_name: str | None = None
    provider: str | None = None
    model_version: str | None = None
    response_time: float | None = None
    rag_warnings: tuple[str, ...] = ()
    reasoning: str | None = field(default=None, repr=False, compare=False)
    compatibility_payload: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.answer_status not in _VALID_ANSWER_STATUSES:
            raise ValueError(f"Unsupported answer_status: {self.answer_status}")

    def to_legacy_payload(self) -> dict[str, Any]:
        """为旧 QA route 保留字段，同时补充 v2 元数据。"""
        payload = dict(self.compatibility_payload)
        payload.update({
            "answer": self.answer,
            "reasoning": self.reasoning,
            "sources": payload.get("sources") or [
                reference.to_manifest_dict()
                for reference in self.citations.references
            ],
            "confidence": self.confidence,
            "model_name": self.model_name,
            "provider": self.provider,
            "model_version": self.model_version,
            "response_time": self.response_time,
            "rag_warnings": list(self.rag_warnings),
            "answer_status": self.answer_status,
            "citations": self.citations.to_dict(),
            "retrieval_summary": self.trace.to_storage_dict(),
            "trace_id": self.trace.trace_id,
            "pipeline_version": self.trace.pipeline_version_key,
        })
        return payload

__all__ = [
    "AnswerStatus",
    "Candidate",
    "CitationManifest",
    "EvidencePack",
    "EvidenceReference",
    "RagExecutionRequest",
    "RagExecutionResult",
    "RetrievalPath",
    "RetrievalTrace",
]