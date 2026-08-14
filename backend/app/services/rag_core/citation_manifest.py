# -*- coding: utf-8 -*-
"""本次 Evidence Pack 的稳定 Citation Manifest 构造器。"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json

from app.services.rag_core.contracts import CitationManifest, EvidencePack, EvidenceReference

DEFAULT_PUBLIC_CORPUS_VERSION = "knowledge_embeddings-v1"
DEFAULT_PUBLIC_COLLECTION = "knowledge_embeddings"


class CitationManifestBuilder:
    """用可定位元数据生成稳定 citation ID，正文永远不参与身份计算。"""

    def __init__(
        self,
        *,
        collection_name: str = DEFAULT_PUBLIC_COLLECTION,
        default_corpus_version: str = DEFAULT_PUBLIC_CORPUS_VERSION,
    ) -> None:
        self._collection_name = _required_identifier(collection_name, "collection_name")
        self._default_corpus_version = _required_identifier(
            default_corpus_version,
            "default_corpus_version",
        )

    def build(self, evidence_pack: EvidencePack) -> CitationManifest:
        """按 Evidence Pack 顺序生成去重后的稳定引用清单。"""
        references: list[EvidenceReference] = []
        seen_identities: set[tuple[str, str, str, str, int, int]] = set()
        for reference in evidence_pack.references:
            identity = citation_identity(
                reference,
                collection_name=self._collection_name,
                default_corpus_version=self._default_corpus_version,
            )
            if identity in seen_identities:
                continue
            seen_identities.add(identity)
            references.append(
                replace(
                    reference,
                    citation_id=citation_id_for_identity(identity),
                    chunk_id=identity[3],
                    corpus_version=identity[1],
                )
            )
        return CitationManifest(references=tuple(references))


def citation_identity(
    reference: EvidenceReference,
    *,
    collection_name: str = DEFAULT_PUBLIC_COLLECTION,
    default_corpus_version: str = DEFAULT_PUBLIC_CORPUS_VERSION,
) -> tuple[str, str, str, str, int, int]:
    """返回不含正文的稳定引用身份，用于 ID 计算与重复判断。"""
    document_id = _required_identifier(reference.document_id, "document_id")
    start_line = _required_line(reference.start_line, "start_line")
    end_line = _required_line(reference.end_line, "end_line")
    if end_line < start_line:
        raise ValueError("end_line cannot be smaller than start_line")
    corpus_version = _optional_identifier(reference.corpus_version) or _required_identifier(
        default_corpus_version,
        "default_corpus_version",
    )
    chunk_id = _optional_identifier(reference.chunk_id) or f"lines-{start_line}-{end_line}"
    normalized_collection = _required_identifier(collection_name, "collection_name")
    return (
        normalized_collection,
        corpus_version,
        document_id,
        chunk_id,
        start_line,
        end_line,
    )


def citation_id_for_identity(identity: tuple[str, str, str, str, int, int]) -> str:
    """从可公开的定位身份生成短哈希引用 ID。"""
    payload = {
        "collection": identity[0],
        "corpus_version": identity[1],
        "document_id": identity[2],
        "chunk_id": identity[3],
        "start_line": identity[4],
        "end_line": identity[5],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"C-{digest}"


def _required_identifier(value: object, field_name: str) -> str:
    normalized = _optional_identifier(value)
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    return normalized


def _optional_identifier(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _required_line(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive integer")
    try:
        line = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer") from exc
    if line <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return line


__all__ = [
    "CitationManifestBuilder",
    "DEFAULT_PUBLIC_COLLECTION",
    "DEFAULT_PUBLIC_CORPUS_VERSION",
    "citation_id_for_identity",
    "citation_identity",
]
