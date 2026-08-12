# -*- coding: utf-8 -*-
"""T07 ContextAssembler 测试：优先级、Tool Result 可见性、裁剪与预算审批。"""
from __future__ import annotations

from app import db
from app.models.agent_items import AgentItem
from app.models.agent_runtime import (
    AgentPlan,
    AgentRun,
)
from app.models.conversation import AgentConversation
from app.services.security_agent.loop.context_assembler import ContextAssembler


def _make_context(app, *, goal="检查越权", mode="hybrid", summary=None):
    with app.app_context():
        conversation = AgentConversation(
            workspace_id=1,
            project_id=1,
            title="会话",
            created_by=1,
        )
        db.session.add(conversation)
        db.session.flush()
        run = AgentRun(
            workspace_id=1,
            project_id=1,
            snapshot_id=1,
            created_by=1,
            goal_text=goal,
            mode=mode,
            max_tool_calls=30,
            max_llm_calls=10,
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(
            run_id=run.id,
            plan_version=1,
            planner_source="rule_based_policy",
            objective=goal,
        )
        db.session.add(plan)
        db.session.flush()
        if summary is not None:
            from app.models.agent_control import AgentConversationSummary

            db.session.add(
                AgentConversationSummary(
                    conversation_id=conversation.id,
                    summary_version=1,
                    source_sequence_from=1,
                    source_sequence_to=5,
                    summary_json=summary,
                    content_digest="abc123",
                )
            )
        db.session.commit()
        return run.id, conversation.id


def test_pack_contains_goal_mode_and_identity(app):
    run_id, conversation_id = _make_context(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        pack = ContextAssembler().build(run, conversation_id=conversation_id)
        assert pack["schema_version"] == 1
        assert pack["conversation"]["conversation_id"] == conversation_id
        assert pack["conversation"]["run_id"] == run.id
        assert pack["conversation"]["mode"] == "hybrid"
        assert pack["goal"] == "检查越权"
        assert pack["plan"]["version"] == 1


def test_recent_user_message_appears_in_pack(app):
    run_id, conversation_id = _make_context(app)
    with app.app_context():
        from app.models.conversation import AgentConversationMessage

        run = db.session.get(AgentRun, run_id)
        db.session.add(
            AgentConversationMessage(
                conversation_id=conversation_id,
                client_message_id="msg-1",
                message_sequence=1,
                role="user",
                message_type="follow_up",
                content_redacted="继续检查水平越权",
                content_digest="d1",
            )
        )
        db.session.commit()
        pack = ContextAssembler().build(run, conversation_id=conversation_id)
        assert any("继续检查水平越权" in message["content"] for message in pack["recent_messages"])


def test_control_input_priority_over_old_summary(app):
    """安全边界与当前 Control Input 优先级高于旧摘要（spec 8.2）。"""
    run_id, conversation_id = _make_context(
        app,
        summary={
            "goal": "旧目标",
            "verified_facts": ["旧事实"],
            "unresolved": [],
        },
    )
    with app.app_context():
        from app.models.agent_control import AgentControlInput

        run = db.session.get(AgentRun, run_id)
        db.session.add(
            AgentControlInput(
                public_id="ctl-1",
                run_id=run.id,
                conversation_id=conversation_id,
                input_type="user_message",
                client_request_id="req-9",
                payload_json={"content": "新方向：重点检查管理员接口"},
                status="pending",
            )
        )
        db.session.commit()
        pack = ContextAssembler().build(run, conversation_id=conversation_id)
        assert pack["goal"] == "检查越权", "当前目标不能被旧摘要覆盖"
        assert pack["conversation_summary"]["content"]["goal"] == "旧目标"
        assert any(
            "新方向" in message["content"]
            for message in pack["recent_messages"]
        ), "最新 Control Input 的方向必须出现在 recent_messages"


def test_tool_result_and_observation_references_in_pack(app):
    run_id, conversation_id = _make_context(app)
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        db.session.add(
            AgentItem(
                public_id="toolresult-1",
                run_id=run.id,
                item_type="tool_result",
                status="completed",
                summary_json={
                    "tool_name": "get_authentication_map",
                    "status": "succeeded",
                    "summary": "定位 3 个入口",
                },
                sensitive_level="internal",
            )
        )
        db.session.commit()
        pack = ContextAssembler().build(run, conversation_id=conversation_id)
        assert any(
            item["public_id"] == "toolresult-1"
            for item in pack["recent_observations"]
        ) or any(
            item["public_id"] == "toolresult-1"
            for item in pack["completed_actions"]
        )


def test_budget_and_approval_state_in_pack(app):
    run_id, conversation_id = _make_context(app)
    with app.app_context():
        from app.models.agent_approval import (
            AgentApproval,
            ApprovalOperationType,
            ApprovalRiskLevel,
            ApprovalStatus,
        )

        run = db.session.get(AgentRun, run_id)
        db.session.add(
            AgentApproval(
                run_id=run.id,
                workspace_id=1,
                operation_type=ApprovalOperationType.BUDGET_INCREASE.value,
                risk_level=ApprovalRiskLevel.MEDIUM.value,
                reason="预算超限",
                status=ApprovalStatus.PENDING.value,
                requested_by=run.created_by,
                operation_digest="digest-1",
            )
        )
        db.session.commit()
        pack = ContextAssembler().build(run, conversation_id=conversation_id)
        assert pack["budgets"] is not None
        assert any(
            approval["status"] == "pending"
            for approval in pack["pending_approvals"]
        )


def test_truncation_uses_summary_and_keeps_goal(app):
    """超限时先摘要低价值历史，保留当前目标与最近观察。"""
    run_id, conversation_id = _make_context(
        app,
        goal="检查鉴权与水平越权，重点覆盖管理员接口、会话管理和令牌校验链路，"
        "需要读取路由守卫、权限校验和认证中间件的完整调用链。",
    )
    with app.app_context():
        run = db.session.get(AgentRun, run_id)
        db.session.add(
            AgentItem(
                public_id="obs-1",
                run_id=run.id,
                item_type="observation",
                status="completed",
                summary_json={"summary": "疑似水平越权"},
                sensitive_level="internal",
            )
        )
        db.session.commit()
        pack = ContextAssembler().build(
            run,
            conversation_id=conversation_id,
            max_context_chars=50,
        )
        assert pack["goal"] == run.goal_text
        assert pack["truncated"] is True
        assert pack["warning_codes"] == ["AGENT_CONTEXT_LIMITED"]
