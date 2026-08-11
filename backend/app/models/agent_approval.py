# -*- coding: utf-8 -*-
"""A7 审批模型：危险操作审批请求（防重放 digest、单次使用、可过期）。"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from app import db


def _enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class ApprovalOperationType(str, Enum):
    BUDGET_INCREASE = "budget_increase"
    REMOTE_SOURCE_SEND = "remote_source_send"
    REMEDIATION_GENERATION = "remediation_generation"


class ApprovalRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELED = "canceled"


class AgentApproval(db.Model):
    __tablename__ = "agent_approvals"
    __table_args__ = (
        db.UniqueConstraint("operation_digest", name="uq_agent_approvals_digest"),
        db.Index("ix_agent_approvals_run", "run_id"),
        db.Index("ix_agent_approvals_workspace", "workspace_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    operation_type = db.Column(db.String(64), nullable=False)
    risk_level = db.Column(db.String(16), nullable=False, default=ApprovalRiskLevel.MEDIUM.value)
    reason = db.Column(db.String(1000), nullable=False)
    affected_scope_json = db.Column(db.JSON)
    operation_digest = db.Column(db.String(64), nullable=False)
    proposed_json = db.Column(db.JSON)
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    status = db.Column(
        db.Enum(ApprovalStatus, name="agent_approval_status", values_callable=_enum_values),
        nullable=False,
        default=ApprovalStatus.PENDING.value,
    )
    decision_comment = db.Column(db.String(1000))
    resolver_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    expires_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    run = db.relationship("AgentRun")

    def to_dict(self) -> dict:
        status = self.status.value if isinstance(self.status, Enum) else self.status
        return {
            "id": self.id,
            "run_id": self.run_id,
            "workspace_id": self.workspace_id,
            "operation_type": self.operation_type,
            "risk_level": self.risk_level,
            "reason": self.reason,
            "affected_scope": self.affected_scope_json or {},
            "operation_digest": self.operation_digest,
            "proposed": self.proposed_json or {},
            "requested_by": self.requested_by,
            "status": status,
            "decision_comment": self.decision_comment,
            "resolver_id": self.resolver_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
