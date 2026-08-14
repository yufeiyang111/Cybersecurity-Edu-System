# -*- coding: utf-8 -*-
"""确定性 QueryNormalizer 与公共 RAG 候选检索器。"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.config import Config
from app.services.rag_core.contracts import Candidate

_TOKEN = re.compile(
    r"\b(?:CVE-\d{4}-\d{4,}|CWE-\d+|--?[A-Za-z][\w-]*|[A-Za-z_][\w.-]*\.[\w.-]+)\b",
    re.IGNORECASE,
)
_PORT = re.compile(r"\b(?:(\d{2,5})\s*(?:端口|port)|port\s*(\d{2,5}))\b", re.IGNORECASE)


@dataclass(frozen=True)
class NormalizedQuery:
    original: str
    normalized: str
    identifiers: tuple[str, ...]

    def trace_summary(self) -> dict[str, Any]:
        return {"identifier_count": len(self.identifiers)}


class QueryNormalizer:
    """第一期仅执行 Unicode 和空白规范化，不进行 LLM 改写。"""

    def normalize(self, query: str) -> NormalizedQuery:
        if not isinstance(query, str):
            raise ValueError("RAG query must be a string")
        normalized = " ".join(unicodedata.normalize("NFKC", query).split())
        tokens = [*_TOKEN.findall(normalized)]
        tokens.extend(
            f"port:{next(value for value in match if value)}"
            for match in _PORT.findall(normalized)
        )
        return NormalizedQuery(
            original=query,
            normalized=normalized,
            identifiers=tuple(dict.fromkeys(token.lower() for token in tokens)),
        )


@dataclass(frozen=True)
class CandidateRetrievalResult:
    candidates: tuple[Candidate, ...]
    normalized_query: NormalizedQuery
    warnings: tuple[str, ...] = ()
    degraded: bool = False

    def trace_summary(self) -> dict[str, Any]:
        paths = sorted({candidate.retrieval_path for candidate in self.candidates})
        return {
            **self.normalized_query.trace_summary(),
            "candidate_count": len(self.candidates),
            "warnings": list(self.warnings),
            "degraded": self.degraded,
            "retrieval_paths": {
                path: sum(candidate.retrieval_path == path for candidate in self.candidates)
                for path in paths
            },
        }


class CandidateRetriever:
    """只生成候选；不承担 rerank、Evidence Pack 或回答生成职责。"""

    def __init__(self, backend, normalizer: QueryNormalizer | None = None):
        self._backend = backend
        self._normalizer = normalizer or QueryNormalizer()

    def retrieve(
        self,
        query: str,
        *,
        vector: Sequence[float] | None,
        where: Mapping[str, Any] | None = None,
        top_k: int | None = None,
        embedding_degraded: bool = False,
    ) -> CandidateRetrievalResult:
        normalized = self._normalizer.normalize(query)
        if not normalized.normalized:
            return CandidateRetrievalResult(
                candidates=(),
                normalized_query=normalized,
                warnings=("EMPTY_QUERY",),
                degraded=embedding_degraded,
            )
        limit = min(top_k or Config.RAG_CANDIDATE_TOP_K, Config.RAG_CANDIDATE_TOP_K)
        try:
            hits = self._backend.hybrid_search(
                vector=None if embedding_degraded else vector,
                text=normalized.normalized,
                where=where,
                top_k=limit,
            )
        except Exception:
            return CandidateRetrievalResult(
                candidates=(),
                normalized_query=normalized,
                warnings=("QDRANT_UNAVAILABLE",),
                degraded=True,
            )
        candidates = tuple(_candidate(hit, rank) for rank, hit in enumerate(hits[:limit], 1))
        return CandidateRetrievalResult(
            candidates=candidates,
            normalized_query=normalized,
            degraded=embedding_degraded or any(
                candidate.retrieval_path == "lexical_only_degraded"
                for candidate in candidates
            ),
        )


def _candidate(hit, rank: int) -> Candidate:
    metadata = {**dict(hit.metadata), "vector_point_id": hit.id}
    stage = dict(hit.retrieval_metadata)
    return Candidate(
        document_id=str(metadata.get("doc_id") or hit.id),
        title=str(metadata.get("title") or "未命名文档"),
        source=metadata.get("source"),
        start_line=_int(metadata.get("start_line")),
        end_line=_int(metadata.get("end_line")),
        content=hit.text,
        parent_content=metadata.get("parent_text"),
        dense_score=_float(stage.get("dense_score")),
        dense_rank=_int(stage.get("dense_rank")),
        bm25_score=_float(stage.get("bm25_score")),
        bm25_rank=_int(stage.get("bm25_rank")),
        rrf_score=_float(stage.get("rrf_score")),
        rank=rank,
        retrieval_path=stage.get("retrieval_path") or "unknown",
        metadata=metadata,
    )


def _int(value: Any) -> int | None:
    try:
        return None if value is None or isinstance(value, bool) else int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return None if value is None or isinstance(value, bool) else float(value)
    except (TypeError, ValueError):
        return None