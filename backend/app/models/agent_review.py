# -*- coding: utf-8 -*-
"""A6 Deep Review 观察结论模型：observation + locations + citations。

Observation 默认 unverified，确认/驳回由 A7 审核闭环接管；
本模块只提供持久化结构与只读序列化。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from app import db


def _enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class ObservationStatus(str, Enum):
    UNVERIFIED = "unverified"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"


class ObservationConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ObservationSourceType(str, Enum):
    DEEP_REVIEW = "deep_review"
    MANUAL = "manual"


class AgentObservation(db.Model):
    __tablename__ = "agent_observations"
    __table_args__ = (
        db.Index("ix_agent_observations_run", "run_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    status = db.Column(
        db.Enum(ObservationStatus, name="agent_observation_status", values_callable=_enum_values),
        nullable=False,
        default=ObservationStatus.UNVERIFIED.value,
    )
    cwe_id = db.Column(db.String(32))
    confidence = db.Column(
        db.Enum(ObservationConfidence, name="agent_observation_confidence", values_callable=_enum_values),
        nullable=False,
        default=ObservationConfidence.LOW.value,
    )
    summary = db.Column(db.Text, nullable=False)
    detail_json = db.Column(db.JSON)
    proof_gaps_json = db.Column(db.JSON)
    source_type = db.Column(db.String(32), nullable=False, default=ObservationSourceType.DEEP_REVIEW.value)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    run = db.relationship("AgentRun")
    locations = db.relationship(
        "AgentObservationLocation",
        back_populates="observation",
        cascade="all, delete-orphan",
        order_by="AgentObservationLocation.id",
    )
    citations = db.relationship(
        "AgentObservationCitation",
        back_populates="observation",
        cascade="all, delete-orphan",
        order_by="AgentObservationCitation.id",
    )

    def to_dict(self, include_detail: bool = False) -> dict:
        result = {
            "id": self.id,
            "run_id": self.run_id,
            "title": self.title,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "cwe_id": self.cwe_id,
            "confidence": self.confidence.value if isinstance(self.confidence, Enum) else self.confidence,
            "summary": self.summary,
            "proof_gaps": self.proof_gaps_json or [],
            "source_type": self.source_type,
            "locations": [location.to_dict() for location in self.locations],
            "citations": [citation.to_dict() for citation in self.citations],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_detail:
            result["detail"] = self.detail_json or {}
        return result


class AgentObservationLocation(db.Model):
    __tablename__ = "agent_observation_locations"
    __table_args__ = (
        db.Index("ix_agent_obs_locations_obs", "observation_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    observation_id = db.Column(
        db.Integer,
        db.ForeignKey("agent_observations.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path = db.Column(db.String(1024), nullable=False)
    start_line = db.Column(db.Integer, nullable=False)
    end_line = db.Column(db.Integer)
    role = db.Column(db.String(32), nullable=False, default="evidence")

    observation = db.relationship("AgentObservation", back_populates="locations")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "role": self.role,
        }


class AgentObservationCitation(db.Model):
    __tablename__ = "agent_observation_citations"
    __table_args__ = (
        db.Index("ix_agent_obs_citations_obs", "observation_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    observation_id = db.Column(
        db.Integer,
        db.ForeignKey("agent_observations.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type = db.Column(db.String(32), nullable=False, default="rag")
    document_id = db.Column(db.String(255))
    document_title = db.Column(db.String(500))
    trust_score = db.Column(db.Float)
    injection_flags = db.Column(db.JSON)
    content_digest = db.Column(db.String(64), nullable=False)
    quote_preview = db.Column(db.String(2000))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    observation = db.relationship("AgentObservation", back_populates="citations")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "trust_score": self.trust_score,
            "injection_flags": self.injection_flags or [],
            "content_digest": self.content_digest,
            "quote_preview": self.quote_preview,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
