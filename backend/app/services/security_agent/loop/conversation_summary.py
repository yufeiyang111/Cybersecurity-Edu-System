# -*- coding: utf-8 -*-
"""ConversationSummaryService（T07，spec §8.3）：结构化会话压缩摘要。

摘要只覆盖其声明的 sequence 区间（source_sequence_from/to），带版本号与
SHA-256 digest；摘要生成失败时由 ContextAssembler 缩短 recent window 并
发出 AGENT_CONTEXT_LIMITED，不静默丢关键约束。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app import db
from app.models.agent_control import AgentConversationSummary

_PLAN_DONE_STATUSES = frozenset({"succeeded", "completed", "skipped", "canceled"})


class ConversationSummaryError(ValueError):
    """摘要参数非法或持久化失败。"""


def build_summary_content(context: dict) -> dict:
    """从受限 ContextPack 构建结构化摘要（spec §8.3）。

    包含：目标、已验证事实（最近 Observation）、未解决节点、已完成动作数、
    预算与审批状态、消息预览；不包含源码全文、完整 Tool Result 或完整推理。
    """
    plan = context.get("plan") or {}
    nodes = plan.get("nodes") or []
    unresolved = [
        str(node.get("key"))
        for node in nodes
        if str(node.get("status")) not in _PLAN_DONE_STATUSES
    ][:20]
    observations = [
        str(
            item.get("content_redacted")
            or item.get("summary")
            or item.get("content")
            or ""
        )[:200]
        for item in (context.get("recent_observations") or [])[:5]
    ]
    completed = context.get("completed_actions") or []
    approvals = [
        str(item.get("status")) for item in (context.get("pending_approvals") or [])
    ]
    return {
        "goal": str(context.get("goal") or "")[:500],
        "verified_facts": observations,
        "unresolved_nodes": unresolved,
        "completed_actions_count": len(completed),
        "plan_version": plan.get("version"),
        "budget": context.get("budgets") or {},
        "pending_approvals": approvals,
        "recent_messages_preview": [
            str(item.get("content") or "")[:200]
            for item in (context.get("recent_messages") or [])[:3]
        ],
        "generated_at": datetime.utcnow().isoformat(),
    }


class ConversationSummaryService:
    def create_summary(
        self,
        conversation_id: int,
        source_sequence_from: int,
        source_sequence_to: int,
        content: dict,
    ) -> AgentConversationSummary:
        if not isinstance(content, dict) or not content:
            raise ConversationSummaryError("摘要内容必须是非空对象")
        if not isinstance(source_sequence_from, int) or not isinstance(
            source_sequence_to, int
        ):
            raise ConversationSummaryError("摘要水位必须是整数")
        if not 0 <= source_sequence_from <= source_sequence_to:
            raise ConversationSummaryError("摘要水位区间非法：from 必须小于等于 to")

        latest = self.latest(conversation_id)
        summary_version = (latest.summary_version + 1) if latest is not None else 1
        summary = AgentConversationSummary(
            conversation_id=conversation_id,
            summary_version=summary_version,
            source_sequence_from=source_sequence_from,
            source_sequence_to=source_sequence_to,
            summary_json=content,
            content_digest=_digest(content),
        )
        db.session.add(summary)
        db.session.commit()
        return summary

    def latest(self, conversation_id: int) -> AgentConversationSummary | None:
        return (
            AgentConversationSummary.query.filter_by(
                conversation_id=conversation_id
            )
            .order_by(AgentConversationSummary.summary_version.desc())
            .first()
        )


def _digest(content: dict) -> str:
    raw = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
