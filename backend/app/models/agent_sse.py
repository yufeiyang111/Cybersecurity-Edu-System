# -*- coding: utf-8 -*-
"""Agent SSE 健康统计模型：带水位重连与 replay gap 记录。

纯统计表（迁移 037），用于 spec §19.3 的 SSE 重连/Gap/Resync 率指标；
不参与业务状态机，也不产生 AgentEvent。
"""
from __future__ import annotations

from datetime import datetime

from app import db


class AgentSseHealth(db.Model):
    __tablename__ = "agent_sse_health"
    __table_args__ = (
        db.Index("ix_agent_sse_health_ws_time", "workspace_id", "created_at"),
        db.Index("ix_agent_sse_health_run", "run_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, nullable=False)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    event_type = db.Column(
        db.String(32), nullable=False, default="connect_with_watermark"
    )
    last_event_id = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
