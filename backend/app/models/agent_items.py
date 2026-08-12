"""Persistence model for unified agent timeline items (v2, T02).

AgentItem 是统一时间线 Item 的持久化基础：模型每次决策、工具调用、结果、
Observation、审批、助手消息等都以同一 Item 结构落库，前端按 sequence 渲染。
"""
from __future__ import annotations

from datetime import datetime

from app import db


class AgentItem(db.Model):
    __tablename__ = "agent_items"
    __table_args__ = (
        db.UniqueConstraint("public_id", name="uq_agent_items_public_id"),
        db.Index("ix_agent_items_run_created", "run_id", "created_at"),
        db.Index("ix_agent_items_run_type", "run_id", "item_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(64), nullable=False)
    conversation_id = db.Column(db.Integer, db.ForeignKey("agent_conversations.id"))
    turn_id = db.Column(db.Integer, db.ForeignKey("agent_turns.id"))
    run_id = db.Column(
        db.Integer, db.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    iteration = db.Column(db.Integer, nullable=False, default=0)
    item_type = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="started")
    parent_item_id = db.Column(db.String(64))
    content_redacted = db.Column(db.Text)
    summary_json = db.Column(db.JSON)
    sensitive_level = db.Column(db.String(32), nullable=False, default="internal")
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    run = db.relationship("AgentRun")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "public_id": self.public_id,
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "run_id": self.run_id,
            "iteration": self.iteration,
            "item_type": self.item_type,
            "status": self.status,
            "parent_item_id": self.parent_item_id,
            "content": self.content_redacted,
            "summary": self.summary_json or {},
            "sensitive_level": self.sensitive_level,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
