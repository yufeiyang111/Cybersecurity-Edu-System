"""Persistent user memory extracted from QA interactions.

Modeled after Mem0's user-scoped memory layer: durable facts are extracted
from conversations, stored per user, and retrieved by semantic similarity
before each QA answer when the user enables persistent memory.
"""
from __future__ import annotations

from datetime import datetime

from app import db


class UserMemory(db.Model):
    """One durable fact remembered about a user."""

    __tablename__ = "user_memories"
    __table_args__ = (
        db.Index("ix_user_memories_user_created", "user_id", "created_at"),
        db.Index("ix_user_memories_user_category", "user_id", "category"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content = db.Column(db.String(2000), nullable=False)
    category = db.Column(db.String(32), nullable=False, default="fact")
    source_conversation_id = db.Column(db.Integer)
    source_record_id = db.Column(
        db.Integer, db.ForeignKey("qa_records.id", ondelete="SET NULL")
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "category": self.category,
            "source_conversation_id": self.source_conversation_id,
            "source_record_id": self.source_record_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
