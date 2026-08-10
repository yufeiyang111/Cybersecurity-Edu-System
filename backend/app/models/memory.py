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
    last_reinforced_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)

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
            "last_reinforced_at": (
                self.last_reinforced_at.isoformat() if self.last_reinforced_at else None
            ),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class MemoryFeedback(db.Model):
    """User feedback (useful/useless) on a single memory."""

    __tablename__ = "memory_feedback"
    __table_args__ = (
        db.Index("ix_memory_feedback_memory", "memory_id"),
        db.Index("ix_memory_feedback_user", "user_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    memory_id = db.Column(
        db.Integer, db.ForeignKey("user_memories.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating = db.Column(db.SmallInteger, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class MemoryEntity(db.Model):
    """Named entity mentioned by a memory (person/org/tech/other)."""

    __tablename__ = "memory_entities"
    __table_args__ = (
        db.Index("ix_memory_entities_user_name", "user_id", "name"),
        db.Index("ix_memory_entities_memory", "memory_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    memory_id = db.Column(
        db.Integer, db.ForeignKey("user_memories.id", ondelete="CASCADE")
    )
    name = db.Column(db.String(128), nullable=False)
    entity_type = db.Column(db.String(32), nullable=False, default="other")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class MemoryEntityLink(db.Model):
    """Relation between two memory entities."""

    __tablename__ = "memory_entity_links"
    __table_args__ = (
        db.Index("ix_memory_entity_links_source", "source_entity_id"),
        db.Index("ix_memory_entity_links_target", "target_entity_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_entity_id = db.Column(
        db.Integer, db.ForeignKey("memory_entities.id", ondelete="CASCADE"), nullable=False
    )
    target_entity_id = db.Column(
        db.Integer, db.ForeignKey("memory_entities.id", ondelete="CASCADE"), nullable=False
    )
    relation = db.Column(db.String(64), nullable=False, default="related")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class MemoryDreamAudit(db.Model):
    """Audit trail for Dream consolidation operations (rollback-friendly)."""

    __tablename__ = "memory_dream_audit"
    __table_args__ = (
        db.Index("ix_memory_dream_audit_user", "user_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action = db.Column(db.String(32), nullable=False)
    memory_ids = db.Column(db.String(512))
    detail = db.Column(db.String(2000))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
