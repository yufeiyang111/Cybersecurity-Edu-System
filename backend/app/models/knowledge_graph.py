# -*- coding: utf-8 -*-
"""
知识图谱领域持久化模型（Neo4j 之外需要落 MySQL 的部分）。

图谱节点/边本体在 Neo4j，社区检测结果与社区摘要是派生数据：
- 社区检测本身无状态（每次按图计算，带进程内 TTL 缓存）
- 社区摘要是 LLM 生成结果，成本高，必须持久化（带图谱签名失效校验）
"""
from __future__ import annotations

from datetime import datetime

from app import db


class KnowledgeGraphCommunitySummary(db.Model):
    """GraphRAG 风格社区摘要缓存（LLM 生成，图谱签名变化后失效覆盖）。"""

    __tablename__ = "kg_community_summaries"

    community_id = db.Column(db.String(64), primary_key=True)
    graph_signature = db.Column(db.String(255), nullable=False)
    algorithm = db.Column(db.String(16), nullable=False)
    title = db.Column(db.String(512), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    summary_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        """完整摘要响应（summary_json 结构 + 元信息）。"""
        payload = dict(self.summary_json or {})
        payload.update({
            "community_id": self.community_id,
            "graph_signature": self.graph_signature,
            "algorithm": self.algorithm,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        })
        return payload
