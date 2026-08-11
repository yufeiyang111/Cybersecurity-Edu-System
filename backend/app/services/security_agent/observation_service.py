# -*- coding: utf-8 -*-
"""Observation 服务（A6）：校验通过后的持久化与只读查询。

- create：落库 observation + locations + citations，发 observation.created 事件。
- 默认 status=unverified，不伪装成已确认漏洞。
- 查询：列表服务端分页、详情带 locations/citations。
"""
from __future__ import annotations

from app import db
from app.models.agent_review import (
    AgentObservation,
    AgentObservationCitation,
    AgentObservationLocation,
    ObservationSourceType,
    ObservationStatus,
)
from app.models.agent_runtime import AgentRun
from app.services.agent_observability import AgentLogger
from app.services.security_agent.contracts import EVENT_OBSERVATION_CREATED
from app.services.security_agent.event_service import EventService
from app.services.security_agent.observation_validator import validate_observation

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class ObservationService:
    def __init__(self, events: EventService | None = None) -> None:
        self._events = events or EventService()
        self._agent_log = AgentLogger()

    # ------------------------------------------------------------------ create

    def create(
        self,
        run: AgentRun,
        payload: dict,
        *,
        source_type: str = ObservationSourceType.DEEP_REVIEW.value,
        trace_id: str | None = None,
    ) -> AgentObservation:
        normalized = validate_observation(payload)
        observation = AgentObservation(
            run_id=run.id,
            title=normalized["title"],
            status=ObservationStatus.UNVERIFIED.value,
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

        self._events.emit(
            run,
            EVENT_OBSERVATION_CREATED,
            {
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


def _float_or_none(value) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None
