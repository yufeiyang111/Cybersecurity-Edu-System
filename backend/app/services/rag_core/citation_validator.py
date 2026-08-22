# -*- coding: utf-8 -*-
"""服务端 Citation Manifest 验证：拒绝伪造、跨请求和不可定位引用。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from app.services.rag_core.contracts import CitationManifest, EvidenceReference

CitationAnswerStatus = Literal[
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "ungrounded",
    "degraded",
]
_VALID_ANSWER_STATUSES = {
    "supported",
    "insufficient_evidence",
    "conflicting_evidence",
    "ungrounded",
    "degraded",
}


@dataclass(frozen=True)
class CitationClaim:
    """模型声明的关键主张及其本次回答使用的 citation ID。"""

    text: str
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class CitationValidationResult:
    """只包含安全错误码的验证结果，不携带原始模型输出。"""

    is_valid: bool
    errors: tuple[str, ...]
    valid_citation_ids: tuple[str, ...]


class CitationValidator:
    """校验主张引用只能来自本次 Evidence Pack 的可定位引用。"""

    def validate(
        self,
        *,
        answer_status: str,
        claims: Sequence[CitationClaim],
        citation_manifest: CitationManifest,
    ) -> CitationValidationResult:
        """验证 citation 归属、定位信息与 supported 回答完整性。"""
        errors: list[str] = []
        references, duplicate_ids = _references_by_id(citation_manifest)
        if duplicate_ids:
            return CitationValidationResult(
                is_valid=False,
                errors=("DUPLICATE_MANIFEST_CITATION",),
                valid_citation_ids=(),
            )
        if answer_status not in _VALID_ANSWER_STATUSES:
            _append_unique(errors, "INVALID_ANSWER_STATUS")
        if answer_status == "supported" and not claims:
            _append_unique(errors, "SUPPORTED_WITHOUT_CLAIMS")

        valid_ids: list[str] = []
        for claim in claims:
            claim_text = claim.text.strip() if isinstance(claim.text, str) else ""
            if not claim_text:
                _append_unique(errors, "EMPTY_CLAIM")
            citation_ids = _normalized_citation_ids(claim.citation_ids)
            if answer_status == "supported" and not citation_ids:
                _append_unique(errors, "SUPPORTED_CLAIM_WITHOUT_CITATION")
                continue
            for citation_id in citation_ids:
                reference = references.get(citation_id)
                if reference is None:
                    _append_unique(errors, "UNKNOWN_CITATION")
                    continue
                if not _is_locatable(reference):
                    _append_unique(errors, "UNLOCATABLE_CITATION")
                    continue
                if citation_id not in valid_ids:
                    valid_ids.append(citation_id)

        return CitationValidationResult(
            is_valid=not errors,
            errors=tuple(errors),
            valid_citation_ids=tuple(valid_ids),
        )


def _references_by_id(
    citation_manifest: CitationManifest,
) -> tuple[dict[str, EvidenceReference], set[str]]:
    references: dict[str, EvidenceReference] = {}
    duplicate_ids: set[str] = set()
    for reference in citation_manifest.references:
        citation_id = str(reference.citation_id or "").strip()
        if not citation_id:
            duplicate_ids.add("")
            continue
        if citation_id in references:
            duplicate_ids.add(citation_id)
            continue
        references[citation_id] = reference
    return references, duplicate_ids


def _normalized_citation_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        return ()
    normalized: list[str] = []
    for citation_id in value:
        if not isinstance(citation_id, str):
            continue
        citation_id = citation_id.strip()
        if citation_id and citation_id not in normalized:
            normalized.append(citation_id)
    return tuple(normalized)


def _is_locatable(reference: EvidenceReference) -> bool:
    document_id = str(reference.document_id or "").strip()
    return (
        bool(document_id)
        and isinstance(reference.start_line, int)
        and isinstance(reference.end_line, int)
        and reference.start_line > 0
        and reference.end_line >= reference.start_line
    )


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


__all__ = [
    "CitationClaim",
    "CitationValidationResult",
    "CitationValidator",
]
