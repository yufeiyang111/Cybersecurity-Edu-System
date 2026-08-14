# -*- coding: utf-8 -*-
"""Evidence Pack 的纯筛选与合并策略。"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Callable, Sequence

from app.services.rag_core.contracts import Candidate


@dataclass(frozen=True)
class EvidenceWindow:
    """通过安全筛选的单个可定位证据窗口。"""

    candidate: Candidate
    content: str
    input_index: int


@dataclass(frozen=True)
class MergedEvidence:
    """一个或多个相邻窗口合成后的可引用证据。"""

    candidate: Candidate
    content: str
    start_line: int
    end_line: int
    input_index: int


def collect_safe_windows(
    candidates: Sequence[Candidate],
    *,
    warnings: list[str],
    rejected: Counter[str],
    injection_detector: Callable[[object], bool],
) -> list[EvidenceWindow]:
    """过滤空、不可定位、注入和相似重复的候选窗口。"""
    windows: list[EvidenceWindow] = []
    retained_contents: list[str] = []
    for index, candidate in enumerate(candidates):
        content = window_content(candidate, warnings)
        if not content:
            rejected["empty_content"] += 1
            continue
        if not has_location(candidate):
            rejected["missing_location"] += 1
            continue
        if injection_detector(f"{candidate.title}\n{content}"):
            rejected["prompt_injection"] += 1
            append_unique(warnings, "INJECTION_FILTERED")
            continue
        if is_duplicate(content, retained_contents):
            rejected["duplicate"] += 1
            append_unique(warnings, "DUPLICATE_EVIDENCE_FILTERED")
            continue
        retained_contents.append(content)
        windows.append(
            EvidenceWindow(
                candidate=candidate,
                content=content,
                input_index=index,
            )
        )
    return windows


def window_content(candidate: Candidate, warnings: list[str]) -> str:
    """优先父窗口；缺失时保留可定位的最小 chunk 窗口。"""
    parent_content = (candidate.parent_content or "").strip()
    if parent_content:
        return parent_content
    append_unique(warnings, "PARENT_TEXT_MISSING")
    return candidate.content.strip()


def has_location(candidate: Candidate) -> bool:
    """引用必须有合法行号范围，避免不可追溯的答案依据。"""
    return (
        isinstance(candidate.start_line, int)
        and isinstance(candidate.end_line, int)
        and candidate.start_line > 0
        and candidate.end_line >= candidate.start_line
    )


def merge_adjacent_windows(windows: Sequence[EvidenceWindow]) -> list[MergedEvidence]:
    """同文档、相邻或重叠行号的窗口合并为一个可定位引用。"""
    by_document: dict[str, list[EvidenceWindow]] = {}
    for window in windows:
        by_document.setdefault(window.candidate.document_id, []).append(window)

    merged: list[MergedEvidence] = []
    for document_windows in by_document.values():
        ordered = sorted(
            document_windows,
            key=lambda item: (
                int(item.candidate.start_line),
                int(item.candidate.end_line),
                item.input_index,
            ),
        )
        current = ordered[0]
        current_parts = [current.content]
        current_end = int(current.candidate.end_line)
        for window in ordered[1:]:
            start_line = int(window.candidate.start_line)
            if start_line <= current_end + 1:
                current_parts.append(window.content)
                current_end = max(current_end, int(window.candidate.end_line))
                continue
            merged.append(merged_evidence(current, current_parts, current_end))
            current = window
            current_parts = [window.content]
            current_end = int(window.candidate.end_line)
        merged.append(merged_evidence(current, current_parts, current_end))
    return sorted(merged, key=lambda item: item.input_index)


def merged_evidence(
    first: EvidenceWindow,
    contents: Sequence[str],
    end_line: int,
) -> MergedEvidence:
    """构造一个合并后的窗口，并消除父窗口产生的重复正文。"""
    return MergedEvidence(
        candidate=first.candidate,
        content=join_unique_contents(contents),
        start_line=int(first.candidate.start_line),
        end_line=end_line,
        input_index=first.input_index,
    )


def document_limit(
    merged: Sequence[MergedEvidence],
    *,
    max_references: int,
    max_document_share: float,
) -> int:
    """多来源场景限制单文档占比；唯一来源可占满证据包。"""
    if len({item.candidate.document_id for item in merged}) <= 1:
        return max_references
    return max(1, int(max_references * max_document_share))


def is_duplicate(content: str, retained_contents: Sequence[str]) -> bool:
    """用精确与高重叠 token 集抑制重复证据。"""
    normalized = normalized_content(content)
    token_set = content_tokens(normalized)
    for retained in retained_contents:
        retained_normalized = normalized_content(retained)
        if normalized == retained_normalized:
            return True
        retained_tokens = content_tokens(retained_normalized)
        if token_set and retained_tokens:
            overlap = len(token_set & retained_tokens) / len(token_set | retained_tokens)
            if overlap >= 0.92:
                return True
    return False


def normalized_content(content: str) -> str:
    """为重复检测消除大小写与空白差异。"""
    return re.sub(r"\s+", " ", content).strip().lower()


def content_tokens(content: str) -> set[str]:
    """支持英文标记、路径和中文字符的轻量 token 化。"""
    return set(re.findall(r"[a-z0-9_./:-]+|[\u4e00-\u9fff]", content))


def join_unique_contents(contents: Sequence[str]) -> str:
    """合并相邻窗口时避免重复父文本反复进入 Prompt。"""
    unique: list[str] = []
    for content in contents:
        if not is_duplicate(content, unique):
            unique.append(content)
    return "\n\n".join(unique)


def append_unique(values: list[str], value: str) -> None:
    """按首次出现顺序加入 warning，避免重复展示。"""
    if value not in values:
        values.append(value)
