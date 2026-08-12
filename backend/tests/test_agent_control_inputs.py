# -*- coding: utf-8 -*-
"""T07 ControlInputService 测试：幂等入队、事件、优先级、应用/拒绝/取代。"""
from __future__ import annotations

from app import db
from app.models.agent_control import AgentControlInput
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.security_agent.loop.control_inputs import ControlInputService


def _make_run() -> AgentRun:
    run = AgentRun(
        workspace_id=1,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="控制输入测试",
        mode="hybrid",
    )
    db.session.add(run)
    db.session.flush()
    return run


def test_enqueue_creates_pending_control_input_and_event(app):
    with app.app_context():
        run = _make_run()
        service = ControlInputService()
        control = service.enqueue(
            run,
            input_type="user_message",
            payload={"content": "继续检查越权"},
            client_request_id="req-1",
            conversation_id=5,
            created_by=run.created_by,
            trace_id="t-enqueue",
        )
        assert control.status == "pending"
        assert control.client_request_id == "req-1"
        event = AgentEvent.query.filter_by(
            run_id=run.id, event_type="item.user_message.created"
        ).first()
        assert event is not None
        assert event.item_public_id == control.public_id


def test_enqueue_same_client_request_id_is_idempotent(app):
    with app.app_context():
        run = _make_run()
        service = ControlInputService()
        first = service.enqueue(
            run,
            input_type="user_message",
            payload={"content": "重复提交"},
            client_request_id="req-idem",
            trace_id="t-1",
        )
        second = service.enqueue(
            run,
            input_type="user_message",
            payload={"content": "重复提交"},
            client_request_id="req-idem",
            trace_id="t-2",
        )
        assert second.id == first.id
        count = AgentControlInput.query.filter_by(
            run_id=run.id, client_request_id="req-idem"
        ).count()
        assert count == 1


def test_list_pending_has_deterministic_priority(app):
    with app.app_context():
        run = _make_run()
        service = ControlInputService()
        service.enqueue(
            run,
            input_type="user_message",
            payload={"content": "继续"},
            client_request_id="req-msg",
            trace_id="t-1",
        )
        service.enqueue(
            run,
            input_type="cancel",
            payload={},
            client_request_id="req-cancel",
            trace_id="t-2",
        )
        service.enqueue(
            run,
            input_type="approval_result",
            payload={"approval_id": 1, "decision": "approved"},
            client_request_id="req-approval",
            trace_id="t-3",
        )
        pending = service.list_pending(run.id)
        types = [item.input_type for item in pending]
        assert types == ["cancel", "approval_result", "user_message"], (
            "取消必须优先于审批结果与用户消息"
        )


def test_apply_marks_applied_with_iteration(app):
    with app.app_context():
        run = _make_run()
        service = ControlInputService()
        control = service.enqueue(
            run,
            input_type="user_message",
            payload={"content": "继续"},
            client_request_id="req-apply",
            trace_id="t-1",
        )
        service.apply(control, iteration=7, trace_id="t-2")
        reloaded = db.session.get(AgentControlInput, control.id)
        assert reloaded.status == "applied"
        assert reloaded.applied_iteration == 7
        assert reloaded.applied_at is not None


def test_reject_marks_rejected(app):
    with app.app_context():
        run = _make_run()
        service = ControlInputService()
        control = service.enqueue(
            run,
            input_type="user_message",
            payload={"content": "被拒绝"},
            client_request_id="req-reject",
            trace_id="t-1",
        )
        service.reject(control, trace_id="t-2")
        reloaded = db.session.get(AgentControlInput, control.id)
        assert reloaded.status == "rejected"


def test_supersede_marks_superseded(app):
    with app.app_context():
        run = _make_run()
        service = ControlInputService()
        control = service.enqueue(
            run,
            input_type="user_message",
            payload={"content": "被取代"},
            client_request_id="req-supersede",
            trace_id="t-1",
        )
        service.supersede(control, trace_id="t-2")
        reloaded = db.session.get(AgentControlInput, control.id)
        assert reloaded.status == "superseded"


def test_apply_skips_already_terminal(app):
    with app.app_context():
        run = _make_run()
        service = ControlInputService()
        control = service.enqueue(
            run,
            input_type="user_message",
            payload={"content": "仅一次"},
            client_request_id="req-once",
            trace_id="t-1",
        )
        service.apply(control, iteration=1, trace_id="t-2")
        service.apply(control, iteration=2, trace_id="t-3")
        reloaded = db.session.get(AgentControlInput, control.id)
        assert reloaded.applied_iteration == 1, "已应用的输入不得重复应用"
