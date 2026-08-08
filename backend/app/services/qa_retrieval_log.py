"""QA 检索落库服务：每次问答的检索结果写入 qa_retrieval_logs，供离线评估与事后分析。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from app import db
from app.models.qa import QaRetrievalLog

logger = logging.getLogger(__name__)


def serialize_retrieved_docs(retrieved_docs: Optional[list]) -> Optional[list]:
    """序列化检索文档（只保留评估/分析需要的字段，不含正文）。"""
    if not retrieved_docs:
        return None
    result = []
    for doc in retrieved_docs[:10]:
        metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
        result.append({
            "doc_id": doc.get("id") if isinstance(doc, dict) else None,
            "title": metadata.get("title", ""),
            "similarity": doc.get("similarity", 0),
            "start_line": metadata.get("start_line", 0),
            "end_line": metadata.get("end_line", 0),
            "source_type": doc.get("source", "unknown"),
        })
    return result


def log_retrieval(
    *,
    user_id: int,
    query: str,
    conversation_id: Optional[int],
    record_id: Optional[int],
    result: Dict[str, Any],
    retrieval_ms: int,
) -> None:
    """写入一条检索日志（失败静默，不影响问答主流程）。"""
    try:
        entry = QaRetrievalLog(
            user_id=user_id,
            query=query[:2000],
            conversation_id=conversation_id,
            record_id=record_id,
            engine_version="enhanced",
            model_name=result.get("model_name"),
            retrieved_docs=json.dumps(
                serialize_retrieved_docs(result.get("retrieved_docs"))
            ),
            sources=json.dumps(result.get("sources") or None),
            retrieval_ms=retrieval_ms,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning("检索日志写入失败: %s", exc)
