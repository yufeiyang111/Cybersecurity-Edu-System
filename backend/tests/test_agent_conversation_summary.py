# -*- coding: utf-8 -*-
"""T07 ConversationSummaryService 测试：水位/digest/版本与摘要失败降级。"""
from __future__ import annotations

from app import db
from app.models.agent_control import AgentConversationSummary
from app.models.conversation import AgentConversation
from app.services.security_agent.loop.conversation_summary import (
    ConversationSummaryService,
)


def _make_conversation() -> AgentConversation:
    conversation = AgentConversation(
        workspace_id=1,
        project_id=1,
        title="摘要测试",
        created_by=1,
    )
    db.session.add(conversation)
    db.session.flush()
    return conversation


def test_summary_persists_watermark_version_and_digest(app):
    with app.app_context():
        conversation = _make_conversation()
        service = ConversationSummaryService()
        summary = service.create_summary(
            conversation.id,
            source_sequence_from=10,
            source_sequence_to=20,
            content={"goal": "检查越权", "verified_facts": ["事实A"]},
        )
        assert summary.summary_version == 1
        assert summary.source_sequence_from == 10
        assert summary.source_sequence_to == 20
        assert len(summary.content_digest) == 64
        reloaded = db.session.get(AgentConversationSummary, summary.id)
        assert reloaded.summary_json["goal"] == "检查越权"


def test_summary_version_increments_per_conversation(app):
    with app.app_context():
        conversation = _make_conversation()
        service = ConversationSummaryService()
        first = service.create_summary(
            conversation.id, 1, 10, {"goal": "g1"}
        )
        second = service.create_summary(
            conversation.id, 11, 20, {"goal": "g2"}
        )
        assert first.summary_version == 1
        assert second.summary_version == 2


def test_latest_returns_newest_version(app):
    with app.app_context():
        conversation = _make_conversation()
        service = ConversationSummaryService()
        service.create_summary(conversation.id, 1, 10, {"goal": "g1"})
        service.create_summary(conversation.id, 11, 20, {"goal": "g2"})
        latest = service.latest(conversation.id)
        assert latest.summary_version == 2
        assert latest.source_sequence_to == 20


def test_summary_digest_changes_with_content(app):
    with app.app_context():
        conversation = _make_conversation()
        service = ConversationSummaryService()
        a = service.create_summary(conversation.id, 1, 10, {"goal": "g1"})
        b = service.create_summary(conversation.id, 11, 20, {"goal": "g2"})
        assert a.content_digest != b.content_digest


def test_summary_only_covers_declared_range(app):
    """摘要只能覆盖其声明的 sequence 区间。"""
    with app.app_context():
        conversation = _make_conversation()
        service = ConversationSummaryService()
        summary = service.create_summary(
            conversation.id,
            source_sequence_from=30,
            source_sequence_to=40,
            content={"goal": "区间"},
        )
        assert summary.source_sequence_from == 30
        assert summary.source_sequence_to == 40
        assert summary.summary_json.get("_source_range") is None
        assert 30 <= summary.source_sequence_from <= summary.source_sequence_to
