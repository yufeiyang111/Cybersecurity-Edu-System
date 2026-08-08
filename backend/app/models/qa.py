"""
问答相关模型
"""
from datetime import datetime
from app import db

class QAConversation(db.Model):
    __tablename__ = "qa_conversations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200))
    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="conversations")
    records = db.relationship("QARecord", back_populates="conversation", cascade="all, delete-orphan")

    def to_dict(self, include_records=False):
        result = {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "is_archived": self.is_archived,
            "record_count": len(self.records),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        if include_records:
            result["records"] = [r.to_dict() for r in self.records]
        return result

class QARecord(db.Model):
    __tablename__ = "qa_records"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("qa_conversations.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    sources = db.Column(db.JSON)
    confidence = db.Column(db.Float)
    model_name = db.Column(db.String(50))
    response_time = db.Column(db.Float)
    rag_warnings = db.Column(db.JSON)
    feedback = db.Column(db.Enum("good", "neutral", "bad"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="qa_records")
    conversation = db.relationship("QAConversation", back_populates="records")
    favorites = db.relationship("Favorite", back_populates="qa_record", cascade="all, delete-orphan")

    def to_dict(self, include_sources=True):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "question": self.question,
            "answer": self.answer,
            "sources": self.sources if include_sources else None,
            "confidence": self.confidence,
            "model_name": self.model_name,
            "response_time": self.response_time,
            "rag_warnings": self.rag_warnings or [],
            "feedback": self.feedback,
            "is_favorited": len(self.favorites) > 0,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class Favorite(db.Model):
    __tablename__ = "favorites"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    qa_record_id = db.Column(db.Integer, db.ForeignKey("qa_records.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="favorites")
    qa_record = db.relationship("QARecord", back_populates="favorites")

    __table_args__ = (db.UniqueConstraint("user_id", "qa_record_id"),)

class FeedbackLog(db.Model):
    __tablename__ = "feedback_logs"
    id = db.Column(db.Integer, primary_key=True)
    qa_record_id = db.Column(db.Integer, db.ForeignKey("qa_records.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    feedback_type = db.Column(db.Enum("good", "neutral", "bad"))
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QaRetrievalLog(db.Model):
    """RAG 检索落库日志（离线评估与检索质量分析）"""
    __tablename__ = "qa_retrieval_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    query = db.Column(db.Text, nullable=False)
    conversation_id = db.Column(db.Integer, db.ForeignKey("qa_conversations.id"))
    record_id = db.Column(db.Integer, db.ForeignKey("qa_records.id"))
    engine_version = db.Column(db.String(64), default="enhanced")
    model_name = db.Column(db.String(64))
    retrieved_docs = db.Column(db.JSON)
    sources = db.Column(db.JSON)
    retrieval_ms = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RagEvalCase(db.Model):
    """RAG 离线评估集（query + 期望命中文档 + 期望答案）"""
    __tablename__ = "rag_eval_cases"
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(500), nullable=False)
    expected_doc_ids = db.Column(db.JSON, nullable=False)
    expected_answer = db.Column(db.Text)
    category = db.Column(db.String(64))
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
