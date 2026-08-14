# -*- coding: utf-8 -*-
"""安全 Evidence Pack 构建：预算选择与脱敏执行摘要。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import logging
from typing import Any, Callable, Literal, Protocol, Sequence

from app.config import Config
from app.services.rag_core.contracts import Candidate, EvidencePack, EvidenceReference
from app.services.rag_core.evidence_policy import (
    MergedEvidence,
    append_unique,
    collect_safe_windows,
    document_limit,
    merge_adjacent_windows,
)
from app.services.rag_guard import is_injected

logger = logging.getLogger(__name__)

EvidenceTokenMode = Literal["tokenizer", "estimate"]
EvidenceAnswerStatus = Literal["supported", "insufficient_evidence"]


class EvidenceTokenCounter(Protocol):
    """Evidence Pack 需要的最小 token 计数接口。"""

    def count_tokens_with_mode(self, text: str) -> tuple[int, EvidenceTokenMode]:
        """返回 token 数与使用的计数模式。"""


@dataclass(frozen=True)
class EvidencePackBuildResult:
    """证据包构建结果；trace 所需字段均不包含正文。"""

    pack: EvidencePack
    answer_status: EvidenceAnswerStatus
    tokenizer_mode: EvidenceTokenMode
    warnings: tuple[str, ...]
    rejection_counts: dict[str, int]

    def trace_summary(self) -> dict[str, Any]:
        """生成可持久化的脱敏阶段摘要。"""
        return {
            "answer_status": self.answer_status,
            "reference_count": len(self.pack.references),
            "token_count": self.pack.token_count,
            "token_budget": self.pack.token_budget,
            "tokenizer_mode": self.tokenizer_mode,
            "rejection_counts": dict(self.rejection_counts),
            "warnings": list(self.warnings),
        }


class EvidencePackBuilder:
    """构建仅含安全、可定位、预算受控证据的 Evidence Pack。"""

    def __init__(
        self,
        token_counter: EvidenceTokenCounter | None = None,
        *,
        max_references: int | None = None,
        max_document_share: float = 0.4,
        injection_detector: Callable[[object], bool] = is_injected,
    ) -> None:
        self._token_counter = token_counter
        self._max_references = (
            Config.RAG_EVIDENCE_TOP_K
            if max_references is None
            else max_references
        )
        self._max_document_share = max_document_share
        self._injection_detector = injection_detector
        if self._max_references <= 0:
            raise ValueError("max_references must be positive")
        if not 0 < max_document_share <= 1:
            raise ValueError("max_document_share must be in (0, 1]")

    def build(
        self,
        candidates: Sequence[Candidate],
        *,
        token_budget: int | None = None,
    ) -> EvidencePackBuildResult:
        """按输入排名构建证据包；没有安全可用证据时返回不足状态。"""
        budget = (
            Config.RAG_EVIDENCE_TOKEN_BUDGET
            if token_budget is None
            else token_budget
        )
        if budget <= 0:
            raise ValueError("token_budget must be positive")

        warnings: list[str] = []
        rejected: Counter[str] = Counter()
        windows = collect_safe_windows(
            candidates,
            warnings=warnings,
            rejected=rejected,
            injection_detector=self._injection_detector,
        )
        merged = merge_adjacent_windows(windows)
        selected, token_count, tokenizer_mode = self._select_with_budget(
            merged,
            budget=budget,
            warnings=warnings,
            rejected=rejected,
        )
        pack = EvidencePack(
            references=tuple(selected),
            token_count=token_count,
            token_budget=budget,
        )
        if not selected:
            append_unique(warnings, "INSUFFICIENT_EVIDENCE")
            return EvidencePackBuildResult(
                pack=pack,
                answer_status="insufficient_evidence",
                tokenizer_mode=tokenizer_mode,
                warnings=tuple(warnings),
                rejection_counts=dict(rejected),
            )
        return EvidencePackBuildResult(
            pack=pack,
            answer_status="supported",
            tokenizer_mode=tokenizer_mode,
            warnings=tuple(warnings),
            rejection_counts=dict(rejected),
        )

    def _select_with_budget(
        self,
        merged: Sequence[MergedEvidence],
        *,
        budget: int,
        warnings: list[str],
        rejected: Counter[str],
    ) -> tuple[list[EvidenceReference], int, EvidenceTokenMode]:
        counter = self._counter()
        per_document_limit = document_limit(
            merged,
            max_references=self._max_references,
            max_document_share=self._max_document_share,
        )
        selected: list[EvidenceReference] = []
        per_document: Counter[str] = Counter()
        token_count = 0
        tokenizer_mode: EvidenceTokenMode = "tokenizer"

        for merged_item in merged:
            if len(selected) >= self._max_references:
                break
            document_id = merged_item.candidate.document_id
            if per_document[document_id] >= per_document_limit:
                rejected["document_diversity"] += 1
                append_unique(warnings, "DOCUMENT_DIVERSITY_LIMIT")
                continue
            counted = count_tokens(counter, merged_item.content)
            if counted is None:
                rejected["token_counter_failure"] += 1
                append_unique(warnings, "TOKEN_COUNTER_FAILURE")
                return [], 0, "estimate"
            content_tokens, mode = counted
            if mode == "estimate":
                tokenizer_mode = "estimate"
                append_unique(warnings, "TOKEN_COUNT_ESTIMATED")
            if content_tokens > budget - token_count:
                rejected["token_budget"] += 1
                append_unique(warnings, "EVIDENCE_TOKEN_BUDGET_EXHAUSTED")
                continue
            selected.append(
                EvidenceReference(
                    citation_id=f"C{len(selected) + 1}",
                    document_id=document_id,
                    title=merged_item.candidate.title,
                    source=merged_item.candidate.source,
                    start_line=merged_item.start_line,
                    end_line=merged_item.end_line,
                    chunk_id=_candidate_chunk_id(merged_item.candidate),
                    corpus_version=_candidate_metadata_text(
                        merged_item.candidate,
                        "corpus_version",
                    ),
                    title_path=_candidate_metadata_text(
                        merged_item.candidate,
                        "title_path",
                    ),
                    content=merged_item.content,
                )
            )
            per_document[document_id] += 1
            token_count += content_tokens

        return selected, token_count, tokenizer_mode

    def _counter(self) -> EvidenceTokenCounter:
        if self._token_counter is None:
            from app.services.text_chunker import text_chunker

            self._token_counter = text_chunker
        return self._token_counter


def count_tokens(
    counter: EvidenceTokenCounter,
    content: str,
) -> tuple[int, EvidenceTokenMode] | None:
    """验证计数器输出；异常时以 trace 可见的安全降级处理。"""
    try:
        token_count, mode = counter.count_tokens_with_mode(content)
    except Exception as exc:
        logger.warning(
            "Evidence token counter failed error_type=%s",
            type(exc).__name__,
        )
        return None
    if (
        isinstance(token_count, bool)
        or not isinstance(token_count, int)
        or token_count < 0
        or mode not in {"tokenizer", "estimate"}
    ):
        return None
    return token_count, mode

def _candidate_metadata_text(candidate: Candidate, key: str) -> str | None:
    value = candidate.metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _candidate_chunk_id(candidate: Candidate) -> str | None:
    chunk_id = _candidate_metadata_text(candidate, "chunk_id")
    if chunk_id:
        return chunk_id
    vector_point_id = _candidate_metadata_text(candidate, "vector_point_id")
    if vector_point_id:
        return vector_point_id
    chunk_index = candidate.metadata.get("chunk_index")
    if isinstance(chunk_index, bool) or chunk_index is None:
        return None
    return f"chunk-{chunk_index}"

__all__ = [
    "EvidencePackBuildResult",
    "EvidencePackBuilder",
    "EvidenceTokenCounter",
    "EvidenceTokenMode",
]
