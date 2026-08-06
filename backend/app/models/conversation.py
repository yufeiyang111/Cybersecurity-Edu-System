"""Persistence models for multi-turn agent conversations."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from app import db


def _enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TurnStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class AgentConversation(db.Model):
    """Long-lived workbench conversation for one project security task."""

    __tablename__ = "agent_conversations"
    __table_args__ = (
        db.Index("ix_agent_conversations_workspace_created", "workspace_id", "created_at"),
        db.Index("ix_agent_conversations_project", "project_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("security_projects.id", ondelete="CASCADE"), nullable=False)
    current_snapshot_id = db.Column(db.Integer, db.ForeignKey("project_snapshots.id", ondelete="SET NULL"))
    title = db.Column(db.String(200), nullable=False, default="")
    status = db.Column(
        db.Enum(ConversationStatus, name="agent_conversation_status", values_callable=_enum_values),
        nullable=False,
        default=ConversationStatus.ACTIVE.value,
    )
    message_sequence = db.Column(db.Integer, nullable=False, default=0)
    turn_sequence = db.Column(db.Integer, nullable=False, default=0)
    context_version = db.Column(db.Integer, nullable=False, default=0)
    summary_version = db.Column(db.Integer, nullable=False, default=0)
    last_event_sequence = db.Column(db.Integer, nullable=False, default=0)
    parent_conversation_id = db.Column(db.Integer, db.ForeignKey("agent_conversations.id"))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace = db.relationship("Workspace")
    project = db.relationship("SecurityProject")
    snapshot = db.relationship("ProjectSnapshot")
    turns = db.relationship(
        "AgentTurn",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AgentTurn.turn_sequence",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "current_snapshot_id": self.current_snapshot_id,
            "title": self.title,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "message_sequence": self.message_sequence,
            "turn_sequence": self.turn_sequence,
            "context_version": self.context_version,
            "summary_version": self.summary_version,
            "last_event_sequence": self.last_event_sequence,
            "parent_conversation_id": self.parent_conversation_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentTurn(db.Model):
    """One user input and the execution scope (run) it triggered."""

    __tablename__ = "agent_turns"
    __table_args__ = (
        db.UniqueConstraint("conversation_id", "turn_sequence", name="uq_agent_turns_conversation_seq"),
        db.Index("ix_agent_turns_conversation", "conversation_id"),
        db.Index("ix_agent_turns_run", "run_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False
    )
    turn_sequence = db.Column(db.Integer, nullable=False)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id", ondelete="CASCADE"))
    parent_turn_id = db.Column(db.Integer, db.ForeignKey("agent_turns.id"))
    status = db.Column(
        db.Enum(TurnStatus, name="agent_turn_status", values_callable=_enum_values),
        nullable=False,
        default=TurnStatus.ACTIVE.value,
    )
    input_message_id = db.Column(db.Integer, db.ForeignKey("agent_conversation_messages.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    conversation = db.relationship("AgentConversation", back_populates="turns")
    run = db.relationship("AgentRun")
    parent_turn = db.relationship("AgentTurn", remote_side=[id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "turn_sequence": self.turn_sequence,
            "run_id": self.run_id,
            "parent_turn_id": self.parent_turn_id,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "input_message_id": self.input_message_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentConversationMessage(db.Model):
    """Idempotent conversation message; content is stored redacted with a digest."""

    __tablename__ = "agent_conversation_messages"
    __table_args__ = (
        db.UniqueConstraint("client_message_id", name="uq_conv_messages_client"),
        db.UniqueConstraint("conversation_id", "message_sequence", name="uq_conv_messages_sequence"),
        db.Index("ix_conv_messages_conversation_seq", "conversation_id", "message_sequence"),
    )

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False
    )
    turn_id = db.Column(db.Integer, db.ForeignKey("agent_turns.id"))
    client_message_id = db.Column(db.String(64), nullable=False)
    message_sequence = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(16), nullable=False)
    message_type = db.Column(db.String(32), nullable=False, default="user_goal")
    content_redacted = db.Column(db.Text, nullable=False)
    content_digest = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    conversation = db.relationship("AgentConversation")
    turn = db.relationship("AgentTurn", foreign_keys=[turn_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "client_message_id": self.client_message_id,
            "message_sequence": self.message_sequence,
            "role": self.role,
            "message_type": self.message_type,
            "content": self.content_redacted,
            "content_digest": self.content_digest,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
