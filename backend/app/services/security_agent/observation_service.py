# -*- coding: utf-8 -*-
"""Observation 服务（A6/A7）：校验后的持久化、人工审核与修复 Diff 生成。

- create：落库 observation + locations + citations，发 observation.created 事件。
- 默认 status=unverified，不伪装成已确认漏洞。
- review：confirmed/rejected/needs_more_evidence，决策写 Event + AuditEvent。
- generate_remediation_diff：仅对已确认结论生成受限 Unified Diff（只读展示）。
- 查询：列表服务端分页、详情带 locations/citations。
"""
from __future__ import annotations

from datetime import datetime

from app import db
from app.models.agent_review import (
    AgentObservation,
    AgentObservationCitation,
    AgentObservationLocation,
    ObservationSourceType,
    ObservationStatus,
)
from app.models.agent_runtime import AgentRun
from app.models.security import AuditEvent
from app.services.agent_observability import AgentLogger
from app.services.security_agent.contracts import (
    EVENT_OBSERVATION_REVIEWED,
    EVENT_WARNING_RAISED,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.observation_validator import validate_observation
from app.services.security_agent.timeline.contracts import (
    EVENT_OBSERVATION_CREATED,
)
from app.services.security_agent.timeline.event_writer import EventWriter

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

_REVIEWABLE_STATUSES = {
    ObservationStatus.UNVERIFIED.value,
    ObservationStatus.NEEDS_MORE_EVIDENCE.value,
}


class ObservationReviewError(ValueError):
    pass


class ObservationService:
    def __init__(self, events: EventService | None = None) -> None:
        self._events = events or EventService()
        self._writer = EventWriter()
        self._agent_log = AgentLogger()

    # ------------------------------------------------------------------ create

    def create(
        self,
        run: AgentRun,
        payload: dict,
        *,
        source_type: str = ObservationSourceType.DEEP_REVIEW.value,
        trace_id: str | None = None,
        evidence_scope: tuple[object, ...] | None = None,
    ) -> AgentObservation:
        normalized = validate_observation(
            payload,
            allowed_code_slices=evidence_scope,
            require_code_evidence=(
                source_type == ObservationSourceType.DEEP_REVIEW.value
            ),
        )
        observation = AgentObservation(
            run_id=run.id,
            title=normalized["title"],
            status=(
                ObservationStatus.NEEDS_MORE_EVIDENCE.value
                if normalized["needs_more_evidence"]
                else ObservationStatus.UNVERIFIED.value
            ),
            cwe_id=normalized["cwe_id"],
            confidence=normalized["confidence"],
            summary=normalized["summary"],
            detail_json=normalized["detail"],
            proof_gaps_json=normalized["proof_gaps"],
            source_type=source_type,
        )
        db.session.add(observation)
        db.session.flush()

        for location in normalized["locations"]:
            db.session.add(
                AgentObservationLocation(
                    observation_id=observation.id,
                    file_path=location["file_path"],
                    start_line=location["start_line"],
                    end_line=location["end_line"],
                    role=location["role"],
                )
            )
        for citation in normalized["citations"]:
            db.session.add(
                AgentObservationCitation(
                    observation_id=observation.id,
                    source_type=str(citation.get("source_type") or "rag"),
                    document_id=str(citation.get("document_id") or "") or None,
                    document_title=str(citation.get("document_title") or "")[:500] or None,
                    trust_score=_float_or_none(citation.get("trust_score")),
                    injection_flags=citation.get("injection_flags") or [],
                    content_digest=str(citation.get("content_digest") or "")[:64] or "",
                    quote_preview=str(citation.get("quote_preview") or "")[:2000] or None,
                )
            )
        db.session.flush()

        self._writer.emit(
            run,
            event_type=EVENT_OBSERVATION_CREATED,
            item_id=f"observation_{observation.id}",
            payload={
                "observation_id": observation.id,
                "title": observation.title,
                "confidence": observation.confidence,
                "cwe_id": observation.cwe_id,
                "status": observation.status,
                "location_count": len(normalized["locations"]),
                "citation_count": len(normalized["citations"]),
                "proof_gap_count": len(normalized["proof_gaps"]),
            },
            trace_id=trace_id,
        )
        self._agent_log.observation_created(
            run,
            observation_id=observation.id,
            confidence=observation.confidence,
            location_count=len(normalized["locations"]),
            citation_count=len(normalized["citations"]),
            trace_id=trace_id,
        )
        db.session.commit()
        return observation

    # ------------------------------------------------------------------ read

    def list_for_run(
        self,
        run_id: int,
        *,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[AgentObservation], int]:
        query = AgentObservation.query.filter_by(run_id=run_id).order_by(
            AgentObservation.id.desc()
        )
        total = query.count()
        page_size = min(max(1, page_size), MAX_PAGE_SIZE)
        offset = max(0, page - 1) * page_size
        rows = query.offset(offset).limit(page_size).all()
        return rows, total

    def get_or_none(self, run_id: int, observation_id: int) -> AgentObservation | None:
        return (
            AgentObservation.query.filter_by(
                id=observation_id, run_id=run_id
            ).first()
        )

    # ------------------------------------------------------------------ review

    def review(
        self,
        run: AgentRun,
        observation: AgentObservation,
        *,
        decision: str,
        comment: str = "",
        actor_id: int | None = None,
        trace_id: str | None = None,
    ) -> AgentObservation:
        """人工审核观察结论：confirmed / rejected / needs_more_evidence。

        已终态（confirmed/rejected）的结论不可再变更；决策写 Event + AuditEvent。
        """
        valid = {
            ObservationStatus.CONFIRMED.value,
            ObservationStatus.REJECTED.value,
            ObservationStatus.NEEDS_MORE_EVIDENCE.value,
        }
        if decision not in valid:
            raise ObservationReviewError("decision 必须是 confirmed / rejected / needs_more_evidence")
        current = observation.status.value if hasattr(observation.status, "value") else observation.status
        if current not in _REVIEWABLE_STATUSES:
            raise ObservationReviewError(f"观察结论当前状态（{current}）不可审核")

        observation.status = decision
        detail = dict(observation.detail_json or {})
        detail["review_comment"] = (comment or "")[:1000]
        detail["reviewed_by"] = actor_id
        detail["reviewed_at"] = datetime.utcnow().isoformat(timespec="seconds")
        observation.detail_json = detail
        db.session.add(
            AuditEvent(
                workspace_id=run.workspace_id,
                actor_id=actor_id,
                action="agent_observation.review",
                target_type="agent_observation",
                target_id=observation.id,
                metadata_json={
                    "run_id": run.id,
                    "decision": decision,
                    "comment": (comment or "")[:300],
                },
            )
        )
        db.session.flush()
        self._events.emit(
            run,
            EVENT_OBSERVATION_REVIEWED,
            {
                "observation_id": observation.id,
                "decision": decision,
                "comment": (comment or "")[:300],
            },
            trace_id=trace_id,
        )
        self._agent_log.observation_created(
            run,
            observation_id=observation.id,
            confidence=str(observation.confidence),
            location_count=len(observation.locations),
            citation_count=len(observation.citations),
            trace_id=trace_id,
        )
        db.session.commit()
        return observation

    # ------------------------------------------------------------------ remediation

    def generate_remediation_diff(
        self,
        run: AgentRun,
        observation: AgentObservation,
        *,
        actor_id: int | None = None,
        trace_id: str | None = None,
    ) -> dict:
        """对已确认观察生成受限修复 Diff（LLM 生成 + Unified Diff 校验，仅展示）。

        返回 {"diff": str, "file_paths": [...], "warning_codes": [...]}。
        """
        from app.services.llm.contracts import LLMRequest
        from app.services.llm.provider_selector import resolve_provider_max_tokens, select_provider
        from app.services.security_agent.prompt_templates.remediation_v1 import (
            PROMPT_TEMPLATE_VERSION,
            build_remediation_prompt,
            parse_diff,
            prompt_digest,
        )
        from app.services.security_agent.llm_invocation import (
            USAGE_SOURCE_PROVIDER_REPORTED,
            record_invocation,
        )

        current = observation.status.value if hasattr(observation.status, "value") else observation.status
        if current != ObservationStatus.CONFIRMED.value:
            raise ObservationReviewError("只有已确认的观察结论才能生成修复 Diff")

        code_blocks: list[str] = []
        snapshot = db.session.get(AgentRun, run.id).snapshot
        from app.services.project_security_graph.code_slice import (
            CodeSliceError,
            CodeSliceForbidden,
            read_code_slice,
        )

        for location in observation.locations:
            try:
                payload = read_code_slice(
                    snapshot,
                    location.file_path,
                    location.start_line,
                    location.end_line or location.start_line,
                    "remediation_diff",
                )
            except (CodeSliceForbidden, CodeSliceError):
                continue
            lines = "\n".join(payload["lines"])
            code_blocks.append(
                f"### {location.file_path} 第 {location.start_line}-{payload['end_line']} 行\n{lines}"
            )
        if not code_blocks:
            raise ObservationReviewError("无法读取受影响代码，无法生成修复 Diff")

        provider = select_provider(user_id=run.created_by, operation="remediation")
        if provider is None:
            raise ObservationReviewError("未配置 LLM Provider，无法生成修复 Diff")

        prompt = build_remediation_prompt(
            title=observation.title,
            summary=observation.summary,
            code_blocks=code_blocks,
            max_tokens=resolve_provider_max_tokens(provider, 1200),
        )
        request = LLMRequest(
            prompt=prompt["user_prompt"],
            system_prompt=prompt["system_prompt"],
            temperature=0.2,
            max_tokens=prompt["max_tokens"],
        )
        try:
            response = provider.generate(request)
        except Exception:
            raise ObservationReviewError("修复 Diff Provider 调用失败")
        if not response.is_success:
            raise ObservationReviewError(
                response.warning_code or "修复 Diff Provider 返回失败"
            )

        record_invocation(
            run,
            provider=provider,
            operation="remediation",
            status="success",
            input_tokens=int((response.usage or {}).get("prompt_tokens") or 0),
            output_tokens=int((response.usage or {}).get("completion_tokens") or 0),
            total_tokens=int((response.usage or {}).get("total_tokens") or 0),
            usage_source=USAGE_SOURCE_PROVIDER_REPORTED if response.usage else "estimated",
            latency_ms=response.latency_ms,
            input_digest=prompt_digest(prompt["user_prompt"]),
            output_digest=prompt_digest(response.text) if response.text else None,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
        )
        db.session.flush()

        try:
            diff_text, touched_files = parse_diff(response.text)
        except ValueError as exc:
            self._events.emit(
                run,
                EVENT_WARNING_RAISED,
                {"warning_codes": ["AGENT_PROVIDER_INVALID_RESPONSE"], "reason": str(exc)[:200]},
                trace_id=trace_id,
            )
            raise ObservationReviewError("修复 Diff 输出无法解析") from exc

        allowed_files = {location.file_path for location in observation.locations}
        invalid = [path for path in touched_files if path not in allowed_files]
        if invalid:
            self._events.emit(
                run,
                EVENT_WARNING_RAISED,
                {
                    "warning_codes": ["AGENT_REMEDIATION_SCOPE_VIOLATION"],
                    "files": invalid[:10],
                },
                trace_id=trace_id,
            )
            raise ObservationReviewError("修复 Diff 涉及观察范围之外的文件，已拒绝")

        detail = dict(observation.detail_json or {})
        detail["remediation_diff"] = {
            "diff": diff_text,
            "file_paths": touched_files,
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
            "generated_by": actor_id,
        }
        observation.detail_json = detail
        db.session.add(
            AuditEvent(
                workspace_id=run.workspace_id,
                actor_id=actor_id,
                action="agent_observation.remediation_diff",
                target_type="agent_observation",
                target_id=observation.id,
                metadata_json={"run_id": run.id, "files": touched_files},
            )
        )
        db.session.commit()
        return {"diff": diff_text, "file_paths": touched_files}


def _float_or_none(value) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None
