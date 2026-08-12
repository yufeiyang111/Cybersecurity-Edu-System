# -*- coding: utf-8 -*-
"""ConversationSummaryService（T07，spec §8.3）：结构化会话压缩摘要。

摘要只覆盖其声明的 sequence 区间（source_sequence_from/to），带版本号与
SHA-256 digest；摘要生成失败时由 ContextAssembler 缩短 recent window 并
发出 AGENT_CONTEXT_LIMITED，不静默丢关键约束。
"""
from __future__ import annotations

import hashlib
import json

from app import db
from app.models.agent_control import AgentConversationSummary


class ConversationSummaryError(ValueError):
    """摘要参数非法或持久化失败。"""


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
