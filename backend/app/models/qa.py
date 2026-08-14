"""
问答相关模型
"""
from datetime import datetime
from sqlalchemy.dialects.mysql import MEDIUMTEXT

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
    answer = db.Column(db.Text().with_variant(MEDIUMTEXT, "mysql"))
    reasoning = db.Column(db.Text().with_variant(MEDIUMTEXT, "mysql"))
    sources = db.Column(db.JSON)
    confidence = db.Column(db.Float)
    model_name = db.Column(db.String(50))
    response_time = db.Column(db.Float)
    rag_warnings = db.Column(db.JSON)
    # RAG Core 加性字段：旧记录允许为空，仍按 legacy sources/answer 反序列化。
    answer_status = db.Column(db.String(32))
    citation_manifest_json = db.Column(db.JSON)
    rag_trace_id = db.Column(db.Integer)
    pipeline_version_key = db.Column(db.String(64))
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
            "reasoning": self.reasoning,
            "sources": self.sources if include_sources else None,
            "confidence": self.confidence,
            "model_name": self.model_name,
            "response_time": self.response_time,
            "rag_warnings": self.rag_warnings or [],
            "answer_status": self.answer_status,
            "citations": self.citation_manifest_json,
            "rag_trace_id": self.rag_trace_id,
            "pipeline_version": self.pipeline_version_key,
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
    expected_evidence_json = db.Column(db.JSON)
    expected_status = db.Column(db.String(32))
    difficulty = db.Column(db.String(32))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)




class RagPipelineVersion(db.Model):
    """可复现的 RAG pipeline 配置与模型版本快照（不含密钥或用户数据）。"""
    __tablename__ = "rag_pipeline_versions"
    id = db.Column(db.Integer, primary_key=True)
    version_key = db.Column(db.String(64), nullable=False, unique=True)
    config_json = db.Column(db.JSON, nullable=False)
    prompt_version = db.Column(db.String(64), nullable=False)
    embedding_version = db.Column(db.String(255), nullable=False)
    reranker_version = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RagRetrievalTrace(db.Model):
    """脱敏 RAG 检索 trace；不得写入原问题、文档正文、Prompt 或 CoT。"""
    __tablename__ = "rag_retrieval_traces"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(64))
    record_id = db.Column(db.Integer, db.ForeignKey("qa_records.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    pipeline_version_id = db.Column(db.Integer, db.ForeignKey("rag_pipeline_versions.id"))
    query_fingerprint = db.Column(db.String(64), nullable=False)
    stage_summary_json = db.Column(db.JSON, nullable=False)
    warnings_json = db.Column(db.JSON)
    retrieval_ms = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RagEvaluationRun(db.Model):
    """一次离线评测运行的汇总记录。"""
    __tablename__ = "rag_evaluation_runs"
    id = db.Column(db.Integer, primary_key=True)
    pipeline_version_id = db.Column(db.Integer, db.ForeignKey("rag_pipeline_versions.id"))
    corpus_version = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(32), nullable=False)
    metrics_json = db.Column(db.JSON)
    report_path = db.Column(db.String(500))
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)


class RagEvaluationResult(db.Model):
    """离线评测单 case 的分阶段指标与失败归因。"""
    __tablename__ = "rag_evaluation_results"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("rag_evaluation_runs.id"), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey("rag_eval_cases.id"), nullable=False)
    retrieval_metrics_json = db.Column(db.JSON)
    citation_metrics_json = db.Column(db.JSON)
    answer_metrics_json = db.Column(db.JSON)
    failure_stage = db.Column(db.String(64))
    notes = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
class MemoryEvalCase(db.Model):
    """持久记忆离线评估集（query + 期望命中的记忆内容）"""
    __tablename__ = "memory_eval_cases"
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.Text, nullable=False)
    expected_content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(32), nullable=False, default="fact")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
