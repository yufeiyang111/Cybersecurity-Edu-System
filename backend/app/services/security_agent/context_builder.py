# -*- coding: utf-8 -*-
"""Deep Review 上下文构建器（A6）：多文件 Context Pack + 预算 + 安全校验。

- 文件证据：从高危 finding 文件/方向文件读取受限代码切片（复用 code_slice 门禁，
  路径逃逸/跨快照由底层拒绝），受文件数、行数、总字符三重预算约束。
- RAG 引用：公共知识库检索结果经注入检测（detect_prompt_injection），
  带注入标记的文档剔除出上下文并记录到 injected_out（前端显示 RAG 警告）。
- 输出 DeepReviewContext：files + citations + focus，供 prompt 构建与引用落库。
"""
from __future__ import annotations

from dataclasses import dataclass

from app import db
from app.models.agent_runtime import AgentRun
from app.models.security import ProjectSnapshot, ScanTask, SecurityFinding

DEFAULT_MAX_FILES = 5
DEFAULT_MAX_LINES_PER_FILE = 200
DEFAULT_MAX_TOTAL_CHARS = 8000
DEFAULT_MAX_CITATIONS = 6


@dataclass(frozen=True)
class CodeSliceEvidence:
    file_path: str
    start_line: int
    end_line: int
    lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class CodeEvidenceTarget:
    """一次受限读取的目标文件与可选 finding 行号。"""

    file_path: str
    start_line: int | None = None
    end_line: int | None = None


@dataclass(frozen=True)
class CitationCandidate:
    document_id: str
    document_title: str
    trust_score: float
    injection_flags: tuple[str, ...]
    content_digest: str
    quote_preview: str
    text: str


@dataclass(frozen=True)
class DeepReviewContext:
    focus: str
    entrypoints: tuple[str, ...] = ()
    files: tuple[CodeSliceEvidence, ...] = ()
    citations: tuple[CitationCandidate, ...] = ()
    injected_doc_ids: tuple[str, ...] = ()
    total_chars: int = 0


class DeepReviewContextError(ValueError):
    pass


class ContextBuilder:
    """为一次 Deep Review 组装受限上下文（只读，不落库）。"""

    def build(
        self,
        run: AgentRun,
        *,
        focus: str,
        entrypoints: tuple[str, ...] = (),
        file_hints: tuple[str, ...] = (),
        max_files: int | None = None,
        max_total_chars: int | None = None,
        max_citations: int | None = None,
    ) -> DeepReviewContext:
        normalized_focus = (focus or "").strip()
        if not normalized_focus:
            raise DeepReviewContextError("focus 不能为空")
        if len(normalized_focus) > 500:
            raise DeepReviewContextError("focus 不能超过 500 字符")

        file_limit = max_files or DEFAULT_MAX_FILES
        char_limit = max_total_chars or DEFAULT_MAX_TOTAL_CHARS
        citation_limit = max_citations or DEFAULT_MAX_CITATIONS
        if not 1 <= file_limit <= 20:
            raise DeepReviewContextError("max_files 必须在 1 至 20 之间")
        if not 1000 <= char_limit <= 20000:
            raise DeepReviewContextError("max_total_chars 必须在 1000 至 20000 之间")

        snapshot = db.session.get(ProjectSnapshot, run.snapshot_id)
        if snapshot is None:
            raise DeepReviewContextError("快照不存在，无法构建上下文")

        targets = self._evidence_targets(run, file_hints)
        file_evidence = self._collect_file_evidence(
            snapshot,
            targets,
            file_limit,
            char_limit,
        )

        citations, injected = self._collect_citations(
            normalized_focus, citation_limit
        )
        total_chars = sum(_evidence_char_count(evidence.lines) for evidence in file_evidence)
        return DeepReviewContext(
            focus=normalized_focus,
            entrypoints=tuple(entrypoints or ()),
            files=file_evidence,
            citations=citations,
            injected_doc_ids=tuple(injected),
            total_chars=total_chars,
        )

    # ------------------------------------------------------------------ files

    def _evidence_targets(
        self,
        run: AgentRun,
        file_hints: tuple[str, ...],
    ) -> tuple[CodeEvidenceTarget, ...]:
        if file_hints:
            return tuple(
                CodeEvidenceTarget(file_path=file_path)
                for file_path in file_hints
                if file_path
            )
        return self._high_finding_targets(run)

    def _high_finding_targets(
        self,
        run: AgentRun,
    ) -> tuple[CodeEvidenceTarget, ...]:
        """优先围绕最近扫描中高危 finding 的实际行号构建代码窗口。"""
        task = (
            ScanTask.query.filter_by(snapshot_id=run.snapshot_id)
            .order_by(ScanTask.id.desc())
            .first()
        )
        if task is None:
            return ()
        rows = (
            db.session.query(
                SecurityFinding.file_path,
                SecurityFinding.start_line,
                SecurityFinding.end_line,
            )
            .filter(
                SecurityFinding.task_id == task.id,
                SecurityFinding.severity.in_(["critical", "high"]),
            )
            .order_by(SecurityFinding.id.asc())
            .all()
        )
        seen: set[str] = set()
        targets: list[CodeEvidenceTarget] = []
        for file_path, start_line, end_line in rows:
            if not file_path or file_path in seen:
                continue
            seen.add(file_path)
            targets.append(
                CodeEvidenceTarget(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                )
            )
        return tuple(targets)

    def _collect_file_evidence(
        self,
        snapshot: ProjectSnapshot,
        targets: tuple[CodeEvidenceTarget, ...],
        file_limit: int,
        char_limit: int,
    ) -> tuple[CodeSliceEvidence, ...]:
        from app.services.project_security_graph.code_slice import (
            CodeSliceError,
            CodeSliceForbidden,
            read_code_slice,
            resolve_slice_path,
        )

        evidence: list[CodeSliceEvidence] = []
        total_chars = 0
        for target_spec in targets:
            if len(evidence) >= file_limit or total_chars >= char_limit:
                break
            file_path = target_spec.file_path
            if not file_path or len(file_path) > 512:
                continue
            try:
                target = resolve_slice_path(snapshot, file_path)
                line_count = sum(
                    1
                    for _ in target.open(encoding="utf-8", errors="replace")
                )
            except (CodeSliceForbidden, CodeSliceError, OSError):
                continue
            if line_count <= 0:
                continue

            start_line, end_line = _slice_window(target_spec, line_count)
            try:
                payload = read_code_slice(
                    snapshot,
                    file_path,
                    start_line,
                    end_line,
                    "deep_review",
                )
            except (CodeSliceForbidden, CodeSliceError):
                continue
            lines = _fit_lines_to_char_budget(
                tuple(payload.get("lines") or ()),
                char_limit - total_chars,
            )
            if not lines:
                continue

            actual_end_line = start_line + len(lines) - 1
            total_chars += _evidence_char_count(lines)
            evidence.append(
                CodeSliceEvidence(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=actual_end_line,
                    lines=lines,
                )
            )
        return tuple(evidence)

    # ------------------------------------------------------------------ rag

    def _collect_citations(
        self, query: str, citation_limit: int
    ) -> tuple[tuple[CitationCandidate, ...], tuple[str, ...]]:
        try:
            from app.services.enhanced_rag_engine import (
                detect_prompt_injection,
                get_rag_engine,
            )

            docs = get_rag_engine().retrieve(query, top_k=citation_limit * 2)
        except Exception:
            return (), ()

        candidates: list[CitationCandidate] = []
        injected: list[str] = []
        for doc in docs[: citation_limit * 2]:
            metadata = doc.get("metadata") or {}
            document_id = str(metadata.get("doc_id") or doc.get("id") or "")
            title = str(metadata.get("title") or doc.get("title") or "未知来源")
            text = str(metadata.get("parent_text") or doc.get("text") or "")
            flags = detect_prompt_injection(f"{title}\n{text}")
            if flags:
                injected.append(document_id)
                continue
            candidates.append(
                CitationCandidate(
                    document_id=document_id,
                    document_title=title,
                    trust_score=_trust_score(doc),
                    injection_flags=(),
                    content_digest=_digest(text),
                    quote_preview=text[:400],
                    text=text,
                )
            )
            if len(candidates) >= citation_limit:
                break
        return tuple(candidates), tuple(injected)

    # ------------------------------------------------------------------ text

    def render_context_text(self, context: DeepReviewContext, max_chars: int = 6000) -> str:
        """把上下文渲染为受限文本（供 prompt 使用）。"""
        parts: list[str] = []
        budget = max_chars
        for evidence in context.files:
            block = (
                f"【代码证据】{evidence.file_path} 第 {evidence.start_line}-{evidence.end_line} 行\n"
                + "\n".join(evidence.lines)
            )
            if budget <= 0:
                break
            budget -= len(block)
            parts.append(block)
        for index, citation in enumerate(context.citations, 1):
            block = (
                f"【背景参考 document_id={citation.document_id}】\n"
                f"{citation.document_title}\n{citation.quote_preview}"
            )
            if budget <= 0:
                break
            budget -= len(block)
            parts.append(block)
        return "\n\n".join(parts)


def _slice_window(
    target: CodeEvidenceTarget,
    line_count: int,
) -> tuple[int, int]:
    """在最大 200 行门禁内，为 finding 预留前后文窗口。"""
    if target.start_line is None:
        return 1, min(DEFAULT_MAX_LINES_PER_FILE, line_count)

    finding_start = min(max(1, int(target.start_line)), line_count)
    finding_end = target.end_line or finding_start
    finding_end = min(max(finding_start, int(finding_end)), line_count)
    start_line = max(1, finding_start - 40)
    end_line = min(line_count, finding_end + 40)
    if end_line - start_line + 1 > DEFAULT_MAX_LINES_PER_FILE:
        end_line = start_line + DEFAULT_MAX_LINES_PER_FILE - 1
    return start_line, end_line


def _fit_lines_to_char_budget(
    lines: tuple[str, ...],
    remaining_chars: int,
) -> tuple[str, ...]:
    """保留完整代码行，严格不超过剩余字符预算。"""
    selected: list[str] = []
    used = 0
    for line in lines:
        line_cost = len(line) + (1 if selected else 0)
        if used + line_cost > remaining_chars:
            break
        selected.append(line)
        used += line_cost
    return tuple(selected)


def _evidence_char_count(lines: tuple[str, ...]) -> int:
    return len("\n".join(lines))

def _trust_score(doc: dict) -> float | None:
    similarity = doc.get("similarity")
    if similarity is None:
        return None
    try:
        return round(min(1.0, max(0.0, float(similarity))), 4)
    except (TypeError, ValueError):
        return None


def _digest(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
