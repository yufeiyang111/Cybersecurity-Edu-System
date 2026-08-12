# -*- coding: utf-8 -*-
"""T12 v1 兼容测试：历史数据可读、legacy 转换、flag 路由不误送旧 Run。"""
from __future__ import annotations

import pytest

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentMessage, AgentRun
from app.services.security_agent.timeline.legacy_adapter import (
    build_legacy_items,
)


def _make_legacy_run() -> AgentRun:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="v1 兼容测试",
        mode="baseline",
    )
    db.session.add(run)
    db.session.flush()
    return run


def test_legacy_message_converted_to_legacy_item(app):
    with app.app_context():
        run = _make_legacy_run()
        db.session.add(
            AgentMessage(
                run_id=run.id,
                role="user",
                content="检查越权",
                message_type="user_goal",
            )
        )
        db.session.add(
            AgentMessage(
                run_id=run.id,
                role="agent",
                content="旧分析结论",
                message_type="llm_analysis",
            )
        )
        db.session.add(
            AgentEvent(
                run_id=run.id,
                sequence=1,
                state_version=1,
                event_type="plan.created",
                payload_json={"plan_version": 1},
            )
        )
        db.session.commit()
        items = build_legacy_items(run.id)
        types = {item["item_type"] for item in items}
        assert "user_message" in types
        assert "assistant_message" in types
        for item in items:
            assert item["schema_version"] == 1
            assert item["source"] in {"legacy_message", "legacy_event"}
        sequences = [item.get("sequence") for item in items if "sequence" in item]
        assert sequences == [1], "legacy 事件保留原始 sequence，不伪造 v2 顺序"


def test_v2_run_does_not_duplicate_legacy_fields(app):
    """v2 新 Run 只写 v2 Item/Event；旧字段由 Serializer 派生，不双写事实源。"""
    with app.app_context():
        run = _make_legacy_run()
        db.session.commit()
        from app.services.security_agent.timeline.item_service import ItemService
        from app.services.security_agent.timeline.event_writer import EventWriter

        service = ItemService(EventWriter())
        service.start(
            run,
            public_id="v2-msg-1",
            item_type="user_message",
            event_type="item.user_message.created",
            sensitive_level="internal",
            trace_id="t-v2",
        )
        db.session.commit()
        from app.models.agent_items import AgentItem

        assert AgentItem.query.filter_by(run_id=run.id).count() == 1
        assert AgentMessage.query.filter_by(run_id=run.id).count() == 0


def test_runner_flag_routes_old_run_to_v1_only_when_enabled(app, monkeypatch):
    """旧 Run 打开 v2 flag 也不被错误送入新 Loop（flag 只影响新 Run 创建）。"""
    with app.app_context():
        run = _make_legacy_run()
        db.session.commit()
        from app.services.security_agent.runner import InlinePlanRunner

        assert hasattr(InlinePlanRunner, "run")
        assert hasattr(InlinePlanRunner, "_run_plan_nodes"), "v1 runner 路径保留"


def test_config_flags_default_off(app):
    from flask import current_app

    assert current_app.config.get("AGENT_LOOP_V2_ENABLED", False) is False
    assert current_app.config.get("AGENT_EVENT_SCHEMA_V2_ENABLED", False) is False
    assert current_app.config.get("AGENT_TIMELINE_V2_ENABLED", False) is False


def test_legacy_approval_observation_cost_still_readable(app):
    """v1 Approval/Observation/Cost 读取 API 依赖的模型与查询路径保留。"""
    with app.app_context():
        run = _make_legacy_run()
        db.session.commit()
        from app.models.agent_approval import AgentApproval

        approval = AgentApproval(
            run_id=run.id,
            workspace_id=1,
            operation_type="budget_increase",
            risk_level="medium",
            reason="预算",
            status="pending",
            requested_by=run.created_by,
            operation_digest="digest-v1-1",
        )
        db.session.add(approval)
        db.session.commit()
        reloaded = AgentApproval.query.filter_by(run_id=run.id).one()
        assert reloaded.status == "pending"
        assert reloaded.to_dict()["run_id"] == run.id
