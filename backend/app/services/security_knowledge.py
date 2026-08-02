"""Workspace-scoped governed security knowledge retrieval.

The lexical retriever is always available. A dedicated Chroma-backed index can
be enabled for semantic retrieval, but any vector failure falls back to the
same workspace-filtered lexical results.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any, Iterable

from flask import current_app, has_app_context

from app.config import Config
from app.models.security import SecurityKnowledgeDocument, SecurityKnowledgeSource
from app.services.rag_guard import detect_prompt_injection


_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(\b(?:api[_-]?key|secret(?:[_-]?key)?|token|password|passwd|authorization)\b\s*[:=]\s*)(?:['\"]?)([^\s,'\";}{]+)"
)
_BEARER_PATTERN = re.compile(r"(?i)(\bauthorization\s*:\s*bearer\s+)([^\s,;]+)")
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
_TOKEN_WORD_PATTERN = re.compile(r"[A-Za-z0-9_./:+-]+|[\u4e00-\u9fff]+")


@dataclass(frozen=True)
class KnowledgeCitation:
    document_id: int
    source_id: int
    title: str
    source_name: str
    version: str
    snippet: str
    score: float
    citation_id: str
    trust_score: float = 1.0
    injection_flags: tuple[str, ...] = ()


def _current_embedding_version() -> str:
    """当前 embedding 服务的版本标签，写入向量 payload 元数据用于溯源。"""
    try:
        from app.services.secbert_embedding import get_embedding_service

        service = get_embedding_service()
        model = str(getattr(service, "model_name", "unknown") or "unknown")
        dimension = int(getattr(service, "dimension", 0))
        return f"{model}:dim{dimension}"[:128]
    except Exception:
        return "unknown"


class _VectorKnowledgeAdapter:
    """Small lazy adapter over the configured vector backend (Chroma or Qdrant).

    Tests inject a fake index through SecurityKnowledgeIndex(vector_index=...),
    so they never need an embedding model or a vector server.
    """

    def __init__(self) -> None:
        from app.services.secbert_embedding import get_embedding_service
        from app.services.vector_stores.contracts import SECURITY_KNOWLEDGE_COLLECTION_NAME, to_2d_list
        from app.services.vector_stores.factory import create_vector_backend

        self._to_2d_list = to_2d_list
        self._backend = create_vector_backend(collection_name=SECURITY_KNOWLEDGE_COLLECTION_NAME)
        self._embedding_service = get_embedding_service()

    def upsert(self, *, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]) -> None:
        vectors = self._embedding_service.encode_documents(documents).tolist()
        embedding_version = _current_embedding_version()
        metadatas = [
            {**metadata, "embedding_version": embedding_version} for metadata in metadatas
        ]
        self._backend.upsert(ids=ids, vectors=vectors, texts=documents, metadatas=metadatas)

    def delete(self, *, where: dict[str, Any]) -> None:
        self._backend.delete(where=where)

    def query(self, *, query_texts: list[str], where: dict[str, Any], n_results: int) -> dict[str, Any]:
        vectors = self._embedding_service.encode_query(query_texts[0])
        vector = self._to_2d_list(vectors)[0]
        hits = self._backend.search(vector=vector, where=where, top_k=n_results)
        return {
            "metadatas": [[hit.metadata for hit in hits]],
            "distances": [[hit.distance for hit in hits]],
        }


class SecurityKnowledgeIndex:
    """Optional vector index that always indexes sanitized text only."""

    def __init__(self, *, vector_enabled: bool | None = None, vector_index: Any | None = None) -> None:
        settings = current_app.config if has_app_context() else Config
        self.vector_enabled = bool(
            settings.get("SECURITY_KNOWLEDGE_VECTOR_ENABLED", False)
            if vector_enabled is None and isinstance(settings, dict)
            else getattr(settings, "SECURITY_KNOWLEDGE_VECTOR_ENABLED", False)
            if vector_enabled is None
            else vector_enabled
        )
        self._vector_index = vector_index
        self._vector_unavailable = False

    def _index(self) -> Any | None:
        if not self.vector_enabled or self._vector_unavailable:
            return None
        if self._vector_index is None:
            try:
                self._vector_index = _VectorKnowledgeAdapter()
            except Exception:
                self._vector_unavailable = True
                return None
        return self._vector_index

    def upsert(self, document: SecurityKnowledgeDocument) -> bool:
        index = self._index()
        if index is None or document.source is None:
            return False
        try:
            index.upsert(
                ids=[str(document.id)],
                documents=[_redact_text(_document_text(document))],
                metadatas=[
                    {
                        "document_id": document.id,
                        "source_id": document.source_id,
                        "workspace_id": document.source.workspace_id,
                        "document_version": document.document_version,
                        "embedding_version": _current_embedding_version(),
                    }
                ],
            )
            return True
        except Exception:
            self._vector_unavailable = True
            return False

    def delete(self, document_id: int) -> bool:
        index = self._index()
        if index is None:
            return False
        try:
            index.delete(where={"document_id": document_id})
            return True
        except Exception:
            self._vector_unavailable = True
            return False

    def query(self, *, workspace_id: int, query: str, top_k: int) -> list[int]:
        index = self._index()
        if index is None:
            return []
        try:
            raw = index.query(
                query_texts=[_redact_text(query)],
                where={"workspace_id": workspace_id},
                n_results=top_k,
            )
        except Exception:
            self._vector_unavailable = True
            return []
        metadatas = raw.get("metadatas", [[]]) if isinstance(raw, dict) else [[]]
        first = metadatas[0] if metadatas else []
        document_ids: list[int] = []
        for metadata in first or []:
            try:
                document_id = int(metadata.get("document_id"))
            except (AttributeError, TypeError, ValueError):
                continue
            if document_id not in document_ids:
                document_ids.append(document_id)
        return document_ids


class SecurityKnowledgeRetriever:
    """RAG citation construction that cannot cross workspace ownership boundaries."""

    def __init__(self, *, knowledge_index: SecurityKnowledgeIndex | None = None) -> None:
        self.knowledge_index = knowledge_index or SecurityKnowledgeIndex()

    def retrieve(self, workspace_id: int, query: str, top_k: int) -> list[KnowledgeCitation]:
        if not isinstance(workspace_id, int) or workspace_id <= 0:
            return []
        if not isinstance(top_k, int) or top_k <= 0:
            return []
        query_tokens = _tokens(query)
        if not query_tokens:
            return []

        documents = _eligible_documents(workspace_id)
        scored: list[tuple[float, SecurityKnowledgeDocument]] = []
        for document in documents:
            score = _lexical_score(document, query_tokens, query)
            if score > 0:
                scored.append((score, document))
        scored.sort(key=lambda item: (-item[0], item[1].id))

        vector_ids = self.knowledge_index.query(workspace_id=workspace_id, query=query, top_k=top_k)
        vector_rank = {document_id: index for index, document_id in enumerate(vector_ids)}
        lexical_scores = {document.id: score for score, document in scored}
        eligible_by_id = {document.id: document for document in documents}
        merged: list[tuple[float, SecurityKnowledgeDocument]] = []
        for document_id, rank in vector_rank.items():
            document = eligible_by_id.get(document_id)
            if document is not None:
                lexical_scores[document_id] = lexical_scores.get(document_id, 0.0) + 100.0 - rank
        for document_id, lexical_score in lexical_scores.items():
            document = eligible_by_id.get(document_id)
            if document is not None:
                merged.append((lexical_score, document))
        merged.sort(key=lambda item: (-item[0], item[1].id))
        return [_citation(document, score, query_tokens) for score, document in merged[:top_k]]


def _eligible_documents(workspace_id: int) -> list[SecurityKnowledgeDocument]:
    from datetime import datetime

    now = datetime.utcnow()
    return (
        SecurityKnowledgeDocument.query.join(SecurityKnowledgeSource)
        .filter(SecurityKnowledgeSource.workspace_id == workspace_id)
        .filter(SecurityKnowledgeSource.is_active.is_(True))
        .filter(SecurityKnowledgeDocument.is_active.is_(True))
        .filter((SecurityKnowledgeSource.effective_from.is_(None)) | (SecurityKnowledgeSource.effective_from <= now))
        .filter((SecurityKnowledgeSource.effective_until.is_(None)) | (SecurityKnowledgeSource.effective_until >= now))
        .filter((SecurityKnowledgeDocument.effective_from.is_(None)) | (SecurityKnowledgeDocument.effective_from <= now))
        .filter((SecurityKnowledgeDocument.effective_until.is_(None)) | (SecurityKnowledgeDocument.effective_until >= now))
        .order_by(SecurityKnowledgeDocument.id.asc())
        .all()
    )


def _tokens(text: str) -> tuple[str, ...]:
    if not isinstance(text, str):
        return ()
    normalized = text.casefold().strip()
    tokens: list[str] = []
    for part in _TOKEN_WORD_PATTERN.findall(normalized):
        if re.fullmatch(r"[\u4e00-\u9fff]+", part):
            tokens.append(part)
            tokens.extend(part[index : index + 2] for index in range(max(0, len(part) - 1)))
        elif len(part) >= 2:
            tokens.append(part)
    return tuple(dict.fromkeys(tokens))


def _document_text(document: SecurityKnowledgeDocument) -> str:
    tags = " ".join(str(tag) for tag in (document.tags_json or []) if isinstance(tag, str))
    return "\n".join(filter(None, (document.title, document.summary or "", tags, document.content)))


def _lexical_score(document: SecurityKnowledgeDocument, query_tokens: Iterable[str], raw_query: str) -> float:
    title = (document.title or "").casefold()
    summary = (document.summary or "").casefold()
    content = (document.content or "").casefold()
    tags = " ".join(str(tag) for tag in (document.tags_json or [])).casefold()
    query_normalized = raw_query.casefold().strip()
    score = 0.0
    if query_normalized and query_normalized in title:
        score += 30.0
    if query_normalized and query_normalized in summary:
        score += 12.0
    if query_normalized and query_normalized in content:
        score += 6.0
    for token in query_tokens:
        score += title.count(token) * 8.0
        score += summary.count(token) * 4.0
        score += tags.count(token) * 3.0
        score += content.count(token) * 1.0
    return score


def _citation(document: SecurityKnowledgeDocument, score: float, query_tokens: Iterable[str]) -> KnowledgeCitation:
    source = document.source
    snippet = _snippet(_document_text(document), query_tokens)
    stable = sha256(f"{document.id}:{document.source_id}:{document.document_version}".encode("utf-8")).hexdigest()[:16]
    return KnowledgeCitation(
        document_id=document.id,
        source_id=document.source_id,
        title=document.title,
        source_name=source.name if source is not None else "",
        version=document.document_version,
        snippet=snippet,
        score=round(float(score), 4),
        citation_id=f"knowledge-{document.id}-{stable}",
        trust_score=_trust_score(document, score),
        injection_flags=detect_prompt_injection(_document_text(document)),
    )


def _trust_score(document: SecurityKnowledgeDocument, score: float) -> float:
    """确定性引用可信度：检索得分归一化 + 注入命中惩罚。

    得分上限按词法+向量融合的上界 200 归一化；命中注入模式时大幅折减，
    让下游（Agent prompt 构造）可以据此剔除或降级。
    """
    normalized = min(max(float(score), 0.0), 200.0) / 200.0
    trust = round(0.6 + 0.4 * normalized, 3)
    if detect_prompt_injection(_document_text(document)):
        trust = round(trust * 0.35, 3)
    return trust


def _snippet(text: str, query_tokens: Iterable[str]) -> str:
    safe = _redact_text(text).strip()
    lower = safe.casefold()
    positions = [lower.find(token.casefold()) for token in query_tokens if token and lower.find(token.casefold()) >= 0]
    start = max(0, min(positions) - 120) if positions else 0
    snippet = safe[start : start + 500]
    if start > 0:
        snippet = "…" + snippet
    return snippet[:500]


def _redact_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    redacted = _BEARER_PATTERN.sub(r"\1[REDACTED]", text)
    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1[REDACTED]", redacted)
    return _TOKEN_PATTERN.sub("[REDACTED]", redacted)
