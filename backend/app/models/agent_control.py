"""Persistence models for ordered control inputs and conversation summaries (T02).

AgentControlInput：用户在活跃 Run 中的追加消息、审批结果、暂停/恢复/取消等
控制输入以幂等方式入队，由 Agent Loop 在安全边界读取应用。
AgentConversationSummary：结构化会话压缩摘要，带水位与 digest。
"""
from __future__ import annotations

from datetime import datetime

from app import db


class AgentControlInput(db.Model):
    __tablename__ = "agent_control_inputs"
    __table_args__ = (
        db.UniqueConstraint(
            "run_id", "client_request_id", name="uq_agent_control_inputs_run_request"
        ),
        db.Index("ix_agent_control_inputs_run_status", "run_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(64), nullable=False)
    conversation_id = db.Column(db.Integer, db.ForeignKey("agent_conversations.id"))
    turn_id = db.Column(db.Integer, db.ForeignKey("agent_turns.id"))
    run_id = db.Column(
        db.Integer, db.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    input_type = db.Column(db.String(32), nullable=False)
    client_request_id = db.Column(db.String(64), nullable=False)
    payload_json = db.Column(db.JSON)
    status = db.Column(db.String(32), nullable=False, default="pending")
    applied_iteration = db.Column(db.Integer)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    applied_at = db.Column(db.DateTime)

    run = db.relationship("AgentRun")
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "public_id": self.public_id,
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "run_id": self.run_id,
            "input_type": self.input_type,
            "client_request_id": self.client_request_id,
            "payload": self.payload_json or {},
            "status": self.status,
            "applied_iteration": self.applied_iteration,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }


class AgentConversationSummary(db.Model):
    __tablename__ = "agent_conversation_summaries"
    __table_args__ = (
        db.UniqueConstraint(
            "conversation_id", "summary_version", name="uq_agent_conversation_summaries_version"
        ),
        db.Index("ix_agent_conversation_summaries_conv", "conversation_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("agent_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    summary_version = db.Column(db.Integer, nullable=False)
    source_sequence_from = db.Column(db.Integer, nullable=False)
    source_sequence_to = db.Column(db.Integer, nullable=False)
    summary_json = db.Column(db.JSON, nullable=False)
    content_digest = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    conversation = db.relationship("AgentConversation")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "summary_version": self.summary_version,
            "source_sequence_from": self.source_sequence_from,
            "source_sequence_to": self.source_sequence_to,
            "summary": self.summary_json,
            "content_digest": self.content_digest,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
