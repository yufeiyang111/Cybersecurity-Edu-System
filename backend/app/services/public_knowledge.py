"""共享公共知识库（knowledge_embeddings，与 QA 同源）检索，用于修复建议引用。

与 workspace 私有的 security_knowledge 检索不同：
- 数据源是历史上积累的 77 条公共安全知识（knowledge_items / knowledge_embeddings）；
- 无 workspace 隔离；若工作区没有私有安全知识，公共检索保证引用仍有数据可证明；
- 引用仍带脱敏、注入检测与可信度，避免绕过安全边界。

失败时静默返回空，不抛出，保证修复建议生成链路可用。
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any, Sequence

from app.services.rag_guard import detect_prompt_injection
from app.services.security_knowledge import (
    KnowledgeCitation,
    _redact_text,
    _snippet,
    _tokens,
)


class PublicKnowledgeRetriever:
    """从公共知识库构造 KnowledgeCitation 的检索器。

    ``vector_store`` 可注入（测试用），默认懒加载 legacy 全局 VectorStore 单例，
    它委托到 configure 的 VectorBackend（默认 Qdrant，collection=knowledge_embeddings）。
    """

    def __init__(self, *, vector_store: Any = None, store_factory: Callable[[], Any] | None = None):
        self._vector_store = vector_store
        self._store_factory = store_factory

    def _store(self) -> Any:
        if self._vector_store is None:
            if self._store_factory is not None:
                self._vector_store = self._store_factory()
            else:
                from app.services.vector_store import get_vector_store

                self._vector_store = get_vector_store()
        return self._vector_store

    def retrieve(  # noqa: PLR0913
        self,
        workspace_id: int,
        query: str,
        top_k: int,
    ) -> list[KnowledgeCitation]:
        if not isinstance(query, str) or not query.strip():
            return []
        if not isinstance(top_k, int) or top_k <= 0:
            return []
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        try:
            hits = self._store().search(_redact_text(query), top_k=top_k * 2)
        except Exception:
            hits = []

        citations = [self._citation_from_hit(hit, query_tokens) for hit in hits]
        citations = [citation for citation in citations if citation is not None]
        citations.sort(key=lambda citation: (-citation.score, citation.document_id))
        return citations[:top_k]

    def _citation_from_hit(self, hit: dict[str, Any], query_tokens: Sequence[str]) -> KnowledgeCitation | None:
        raw_id = str(hit.get("id") or "") if isinstance(hit, dict) else ""
        if not raw_id or not _is_positive_int(raw_id):
            return None
        try:
            document_id = int(raw_id)
        except (TypeError, ValueError):
            return None

        metadata = hit.get("metadata") or {}
        title = str(metadata.get("title") or hit.get("title") or "")
        if not title:
            return None
        text = str(hit.get("text") or metadata.get("text") or "")
        try:
            score = float(hit.get("similarity") or 0.0)
        except (TypeError, ValueError):
            score = 0.0

        stable = _citation_id_suffix(document_id, title, text)
        flags = detect_prompt_injection(f"{title}\n{text}")
        return KnowledgeCitation(
            document_id=document_id,
            source_id=0,
            title=title,
            source_name=str(metadata.get("source") or "公共安全知识库"),
            version="v1",
            snippet=_snippet(text, query_tokens),
            score=round(min(max(score, 0.0), 1.0), 4),
            citation_id=f"knowledge-{document_id}-{stable}",
            trust_score=_public_trust_score(score, flags),
            injection_flags=flags,
        )


def _public_trust_score(score: float, injection_flags: tuple[str, ...]) -> float:
    normalized = min(max(float(score), 0.0), 1.0)
    # 公共库没有 0~200 的检索分，用相似度归一化到 0.6~1.0 基线。
    trust = round(0.6 + 0.4 * normalized, 3)
    if injection_flags:
        trust = round(trust * 0.35, 3)
    return trust


def _is_positive_int(value: str) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _citation_id_suffix(document_id: int, title: str, text: str) -> str:
    payload = f"{document_id}:{title}:{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]