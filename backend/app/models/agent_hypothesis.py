# -*- coding: utf-8 -*-
"""Harness V3 审计技能假设与 Critic 判定的持久化模型。"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from app import db


def _enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class AuditHypothesisStatus(str, Enum):
    QUEUED = "queued"
    ACTIVE = "active"
    NEEDS_EVIDENCE = "needs_evidence"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    STOPPED_FOR_BUDGET = "stopped_for_budget"


class AuditHypothesisVerdict(str, Enum):
    CONFIRM_CANDIDATE = "confirm_candidate"
    REQUEST_EVIDENCE = "request_evidence"
    REJECT_HYPOTHESIS = "reject_hypothesis"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    STOP_FOR_BUDGET = "stop_for_budget"


class AgentAuditHypothesis(db.Model):
    """单个 Run 内可审计、无源码的攻击路径候选。"""

    __tablename__ = "agent_audit_hypotheses"
    __table_args__ = (
        db.UniqueConstraint(
            "run_id",
            "hypothesis_key",
            name="uq_agent_audit_hypotheses_run_key",
        ),
        db.Index("ix_agent_audit_hypotheses_run_status", "run_id", "status"),
        db.Index("ix_agent_audit_hypotheses_run_priority", "run_id", "priority"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(
        db.Integer,
        db.ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    hypothesis_key = db.Column(db.String(64), nullable=False)
    skill_key = db.Column(db.String(64), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    target_summary = db.Column(db.String(1000), nullable=False)
    priority = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.Enum(
            AuditHypothesisStatus,
            name="agent_audit_hypothesis_status",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=AuditHypothesisStatus.QUEUED.value,
    )
    planner_source = db.Column(db.String(64), nullable=False)
    required_evidence_json = db.Column(db.JSON, nullable=False)
    authorized_scopes_json = db.Column(db.JSON, nullable=False)
    satisfied_evidence_json = db.Column(db.JSON)
    evidence_gaps_json = db.Column(db.JSON)
    reflection_count = db.Column(db.Integer, nullable=False, default=0)
    execution_attempt_count = db.Column(db.Integer, nullable=False, default=0)
    related_item_public_id = db.Column(db.String(64))
    related_tool_call_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    run = db.relationship("AgentRun")
    verdicts = db.relationship(
        "AgentAuditHypothesisVerdict",
        back_populates="hypothesis",
        cascade="all, delete-orphan",
        order_by="AgentAuditHypothesisVerdict.verdict_version",
    )

    def to_dict(self, include_verdicts: bool = False) -> dict:
        result = {
            "id": self.id,
            "run_id": self.run_id,
            "hypothesis_key": self.hypothesis_key,
            "skill_key": self.skill_key,
            "title": self.title,
            "target_summary": self.target_summary,
            "priority": self.priority,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "planner_source": self.planner_source,
            "required_evidence": self.required_evidence_json or [],
            "authorized_scopes": self.authorized_scopes_json or [],
            "satisfied_evidence": self.satisfied_evidence_json or [],
            "evidence_gaps": self.evidence_gaps_json or [],
            "reflection_count": self.reflection_count,
            "execution_attempt_count": self.execution_attempt_count,
            "related_item_public_id": self.related_item_public_id,
            "related_tool_call_id": self.related_tool_call_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_verdicts:
            result["verdicts"] = [verdict.to_dict() for verdict in self.verdicts]
        return result


class AgentAuditHypothesisVerdict(db.Model):
    """Evidence Critic 对漏洞假设作出的受控、版本化判定。"""

    __tablename__ = "agent_audit_hypothesis_verdicts"
    __table_args__ = (
        db.UniqueConstraint(
            "hypothesis_id",
            "verdict_version",
            name="uq_agent_audit_hypothesis_verdict_version",
        ),
        db.Index("ix_agent_audit_hypothesis_verdicts_hypothesis", "hypothesis_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    hypothesis_id = db.Column(
        db.Integer,
        db.ForeignKey("agent_audit_hypotheses.id", ondelete="CASCADE"),
        nullable=False,
    )
    verdict_version = db.Column(db.Integer, nullable=False)
    verdict = db.Column(
        db.Enum(
            AuditHypothesisVerdict,
            name="agent_audit_hypothesis_verdict",
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    reason_summary = db.Column(db.String(2000), nullable=False)
    evidence_gaps_json = db.Column(db.JSON)
    next_action_json = db.Column(db.JSON)
    critic_version = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    hypothesis = db.relationship("AgentAuditHypothesis", back_populates="verdicts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hypothesis_id": self.hypothesis_id,
            "verdict_version": self.verdict_version,
            "verdict": self.verdict.value if isinstance(self.verdict, Enum) else self.verdict,
            "reason_summary": self.reason_summary,
            "evidence_gaps": self.evidence_gaps_json or [],
            "next_action": self.next_action_json or {},
            "critic_version": self.critic_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }