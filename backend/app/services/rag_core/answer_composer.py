# -*- coding: utf-8 -*-
"""结构化 RAG 回答解析、Citation 验证和 legacy 兼容降级。"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Sequence

from app.services.rag_core.citation_validator import (
    CitationClaim,
    CitationValidationResult,
    CitationValidator,
)
from app.services.rag_core.contracts import CitationManifest

_SAFE_STRICT_REJECTION = "当前模型输出无法通过引用验证，无法提供可验证的回答。"


@dataclass(frozen=True)
class ParsedRagAnswer:
    """从模型 JSON 得到的结构化回答；尚未代表引用已通过验证。"""

    answer_status: str
    answer: str
    claims: tuple[CitationClaim, ...]
    uncertainty: tuple[str, ...]


@dataclass(frozen=True)
class AnswerComposition:
    """可供 RAG 管道使用的回答结果，不保存原始模型响应。"""

    answer: str
    answer_status: str
    citations: CitationManifest
    claims: tuple[CitationClaim, ...]
    uncertainty: tuple[str, ...]
    warnings: tuple[str, ...]
    validation: CitationValidationResult | None = None


class AnswerComposer:
    """把不可信模型输出收敛为受 citation 约束的回答契约。"""

    def __init__(self, validator: CitationValidator | None = None) -> None:
        self._validator = validator or CitationValidator()

    def compose(
        self,
        raw_response: object,
        *,
        citation_manifest: CitationManifest,
        strict_citations: bool,
    ) -> AnswerComposition:
        """解析并校验模型输出；失败时按 strict flag 选择安全兼容路径。"""
        parsed = parse_structured_answer(raw_response)
        if parsed is None:
            return self._unverified_result(
                fallback_answer=_legacy_answer(raw_response),
                citation_manifest=citation_manifest,
                warnings=("STRUCTURED_RESPONSE_PARSE_FAILED",),
                strict_citations=strict_citations,
            )

        validation = self._validator.validate(
            answer_status=parsed.answer_status,
            claims=parsed.claims,
            citation_manifest=citation_manifest,
        )
        if not validation.is_valid:
            return self._unverified_result(
                fallback_answer=parsed.answer,
                citation_manifest=citation_manifest,
                warnings=("CITATION_VALIDATION_FAILED",),
                strict_citations=strict_citations,
                validation=validation,
            )

        return AnswerComposition(
            answer=parsed.answer,
            answer_status=parsed.answer_status,
            citations=CitationManifest(
                references=citation_manifest.references,
                claim_citations=_claim_citations(parsed.claims),
            ),
            claims=parsed.claims,
            uncertainty=parsed.uncertainty,
            warnings=(),
            validation=validation,
        )

    @staticmethod
    def _unverified_result(
        *,
        fallback_answer: str,
        citation_manifest: CitationManifest,
        warnings: tuple[str, ...],
        strict_citations: bool,
        validation: CitationValidationResult | None = None,
    ) -> AnswerComposition:
        final_warnings = list(warnings)
        if strict_citations:
            final_warnings.append("STRICT_CITATION_REJECTED")
            answer = _SAFE_STRICT_REJECTION
        else:
            final_warnings.append("UNVERIFIED_LEGACY_RESPONSE")
            answer = fallback_answer
        return AnswerComposition(
            answer=answer,
            answer_status="degraded",
            citations=CitationManifest(references=citation_manifest.references),
            claims=(),
            uncertainty=(),
            warnings=tuple(final_warnings),
            validation=validation,
        )


def parse_structured_answer(raw_response: object) -> ParsedRagAnswer | None:
    """解析模型 JSON；任一关键字段非法即返回 None，交由安全降级处理。"""
    if not isinstance(raw_response, str):
        return None
    text = _strip_json_fence(raw_response)
    if not text or len(text) > 200_000:
        return None
    try:
        payload = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    answer_status = payload.get("answer_status")
    answer = payload.get("answer")
    claims_payload = payload.get("claims", [])
    uncertainty_payload = payload.get("uncertainty", [])
    if not isinstance(answer_status, str) or not answer_status.strip():
        return None
    if not isinstance(answer, str) or not answer.strip():
        return None
    claims = _parse_claims(claims_payload)
    uncertainty = _parse_uncertainty(uncertainty_payload)
    if claims is None or uncertainty is None:
        return None
    return ParsedRagAnswer(
        answer_status=answer_status.strip(),
        answer=answer.strip(),
        claims=claims,
        uncertainty=uncertainty,
    )


def _parse_claims(value: object) -> tuple[CitationClaim, ...] | None:
    if not isinstance(value, list):
        return None
    claims: list[CitationClaim] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        text = item.get("text")
        citation_ids = item.get("citation_ids")
        if not isinstance(text, str) or not isinstance(citation_ids, list):
            return None
        normalized_ids: list[str] = []
        for citation_id in citation_ids:
            if not isinstance(citation_id, str) or not citation_id.strip():
                return None
            normalized = citation_id.strip()
            if normalized not in normalized_ids:
                normalized_ids.append(normalized)
        claims.append(
            CitationClaim(
                text=text.strip(),
                citation_ids=tuple(normalized_ids),
            )
        )
    return tuple(claims)


def _parse_uncertainty(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    parsed: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        item = item.strip()
        if item and item not in parsed:
            parsed.append(item)
    return tuple(parsed)


def _claim_citations(claims: Sequence[CitationClaim]) -> dict[str, tuple[str, ...]]:
    """为相同主张生成可区分键，保留模型输出的主张文本。"""
    output: dict[str, tuple[str, ...]] = {}
    for index, claim in enumerate(claims, start=1):
        key = claim.text or f"claim-{index}"
        if key in output:
            key = f"{key} #{index}"
        output[key] = claim.citation_ids
    return output


def _legacy_answer(raw_response: object) -> str:
    if isinstance(raw_response, str) and raw_response.strip():
        return raw_response.strip()
    return _SAFE_STRICT_REJECTION


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) < 3 or not lines[-1].strip().startswith("```"):
        return stripped
    return "\n".join(lines[1:-1]).strip()


__all__ = [
    "AnswerComposer",
    "AnswerComposition",
    "ParsedRagAnswer",
    "parse_structured_answer",
]
