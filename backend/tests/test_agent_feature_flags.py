# -*- coding: utf-8 -*-
"""Feature Flag 解析与 v2→v1 回滚翻译测试（spec §22.1/S-01/S-02/S-03/S-06）。"""
from __future__ import annotations

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun, AgentRunStatus
from app.models.security import Workspace
from app.services.security_agent.feature_flags import AgentFeatureFlags
from app.services.security_agent.service import AgentRunService
from app.services.security_agent.timeline.event_writer import EventWriter
from app.services.security_agent.timeline.item_service import ItemService

from test_agent_run_api import auth_headers, make_user


def _make_workspace(name: str, overrides: dict | None = None) -> Workspace:
    workspace = Workspace(
        name=name,
        slug=name,
        agent_feature_flags=overrides,
    )
    db.session.add(workspace)
    db.session.flush()
    return workspace


def _make_run(workspace_id: int) -> AgentRun:
    run = AgentRun(
        workspace_id=workspace_id,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="flag 测试",
        mode="hybrid",
        status=AgentRunStatus.EXECUTING_TOOLS.value,
    )
    db.session.add(run)
    db.session.flush()
    return run


def test_global_flags_default_off(app):
    with app.app_context():
        flags = AgentFeatureFlags().for_workspace(1)
        assert flags.as_dict() == {
            "loop_v2": False,
            "event_schema_v2": False,
            "timeline_v2": False,
        }


def test_workspace_override_enables_flag_even_when_global_off(app):
    """灰度路径：全局关闭时，授权覆盖可为测试 workspace 开启（S-04）。"""
    with app.app_context():
        app.config["AGENT_LOOP_V2_ENABLED"] = False
        workspace = _make_workspace("ws-gray-enable", {"loop_v2": True})
        flags = AgentFeatureFlags().for_workspace(workspace.id)
        assert flags.loop_v2 is True, "授权覆盖可为测试 workspace 开启灰度"


def test_workspace_can_downgrade_enabled_flag(app):
    with app.app_context():
        app.config["AGENT_LOOP_V2_ENABLED"] = True
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True
        app.config["AGENT_TIMELINE_V2_ENABLED"] = True
        downgraded = _make_workspace(
            "ws-downgrade",
            {"loop_v2": False, "timeline_v2": False},
        )
        flags = AgentFeatureFlags().for_workspace(downgraded.id)
        assert flags.loop_v2 is False
        assert flags.event_schema_v2 is True, "未覆盖的 flag 保持全局值"
        assert flags.timeline_v2 is False
        normal = _make_workspace("ws-normal", None)
        flags = AgentFeatureFlags().for_workspace(normal.id)
        assert flags.as_dict() == {
            "loop_v2": True,
            "event_schema_v2": True,
            "timeline_v2": True,
        }



def test_run_snapshot_stays_stable_after_workspace_flag_changes(app):
    """执行中的 Run 必须读取创建时快照，而不是被工作区后来开关改写。"""
    with app.app_context():
        snapshot = {
            "loop_v2": True,
            "event_schema_v2": True,
            "timeline_v2": True,
        }
        workspace = _make_workspace("ws-run-snapshot", dict(snapshot))
        run = _make_run(workspace.id)
        run.feature_flags_snapshot_json = dict(snapshot)
        db.session.flush()

        workspace.agent_feature_flags = {
            "loop_v2": False,
            "event_schema_v2": False,
            "timeline_v2": False,
        }
        db.session.flush()

        assert AgentFeatureFlags().for_run(run).as_dict() == snapshot


def test_legacy_run_falls_back_to_current_workspace_flags_without_snapshot(app):
    """没有创建时快照的历史任务仍可按当前工作区配置兼容读取。"""
    with app.app_context():
        workspace = _make_workspace(
            "ws-legacy-workspace-fallback",
            {
                "loop_v2": False,
                "event_schema_v2": False,
                "timeline_v2": False,
            },
        )
        run = _make_run(workspace.id)

        assert AgentFeatureFlags().for_run(run).as_dict() == {
            "loop_v2": False,
            "event_schema_v2": False,
            "timeline_v2": False,
        }


def test_run_payload_recovers_legacy_v2_execution_from_recorded_events(app):
    """旧任务缺少快照时，以已持久化 v2 事件还原真实执行方式。"""
    with app.app_context():
        workspace = _make_workspace(
            "ws-legacy-observed-v2",
            {
                "loop_v2": False,
                "event_schema_v2": False,
                "timeline_v2": False,
            },
        )
        run = _make_run(workspace.id)
        run.mode = "deep_audit"
        run.iteration_count = 1
        run.llm_call_count = 1
        db.session.add(
            AgentEvent(
                run_id=run.id,
                sequence=1,
                state_version=1,
                event_type="item.reasoning_summary.completed",
                schema_version=2,
                payload_json={"summary": "已完成证据复核"},
            )
        )
        db.session.commit()

        payload = AgentRunService().get_run_payload(run)

        assert payload["feature_flag_source"] == "legacy_observed"
        assert payload["feature_flags"] == {
            "loop_v2": True,
            "event_schema_v2": True,
            "timeline_v2": True,
        }
        assert payload["workspace_feature_flags"] == {
            "loop_v2": False,
            "event_schema_v2": False,
            "timeline_v2": False,
        }
        assert payload["run"]["execution_feature_flag_source"] == "legacy_observed"

def test_event_writer_keeps_v2_when_flag_on(app):
    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = True
        workspace = _make_workspace("ws-v2-on")
        run = _make_run(workspace.id)
        EventWriter().emit(
            run,
            event_type="item.tool_call.started",
            item_id="call-1",
            payload={"name": "run_baseline_scan"},
            trace_id="t-1",
        )
        db.session.commit()
        event = AgentEvent.query.filter_by(run_id=run.id).one()
        assert event.schema_version == 2
        assert event.event_type == "item.tool_call.started"


def test_event_writer_translates_to_v1_when_flag_off(app):
    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = False
        workspace = _make_workspace("ws-v1-translate")
        run = _make_run(workspace.id)
        writer = EventWriter()
        writer.emit(
            run,
            event_type="item.tool_call.started",
            item_id="call-2",
            payload={"name": "run_baseline_scan"},
            trace_id="t-2",
        )
        db.session.commit()
        event = AgentEvent.query.filter_by(run_id=run.id).one()
        assert event.schema_version == 1, "关闭 Event v2 后必须写 v1 协议"
        assert event.event_type == "tool.started"
        assert event.payload_json.get("tool_call_id") == "call-2"
        assert event.payload_json.get("tool_name") == "run_baseline_scan"


def test_assistant_completed_translates_with_authoritative_analysis(app):
    with app.app_context():
        app.config["AGENT_EVENT_SCHEMA_V2_ENABLED"] = False
        workspace = _make_workspace("ws-v1-analysis")
        run = _make_run(workspace.id)
        service = ItemService(EventWriter())
        service.start(
            run,
            public_id="asst-9",
            item_type="assistant_message",
            event_type="item.assistant_message.started",
            sensitive_level="internal",
            trace_id="t-3",
        )
        service.append_delta(
            run,
            "asst-9",
            delta="审查完成。",
            event_type="item.assistant_message.delta",
            trace_id="t-3",
        )
        service.complete(
            run,
            "asst-9",
            event_type="item.assistant_message.completed",
            trace_id="t-3",
        )
        db.session.commit()
        events = (
            AgentEvent.query.filter_by(run_id=run.id)
            .order_by(AgentEvent.sequence.asc())
            .all()
        )
        assert all(event.schema_version == 1 for event in events)
        completed = [event for event in events if event.event_type == "llm.completed"]
        assert len(completed) == 1, "v2 completed 必须翻译为 llm.completed"
        assert completed[0].payload_json.get("analysis") == "审查完成。"


def test_workspace_flag_endpoint_owner_can_enable_and_downgrade(agent_api_app):
    user_id, workspace_id = make_user(agent_api_app, "flagowner", "flagowner@t")
    client = agent_api_app.test_client()
    headers = auth_headers(agent_api_app, user_id)

    response = client.patch(
        f"/api/security/workspaces/{workspace_id}/agent-feature-flags",
        headers=headers,
        json={"overrides": {"loop_v2": True, "timeline_v2": True}},
    )
    assert response.status_code == 200, "owner 可授权开启灰度 flag"
    body = response.get_json()
    assert body["resolved"]["loop_v2"] is True
    assert body["resolved"]["timeline_v2"] is True

    response = client.patch(
        f"/api/security/workspaces/{workspace_id}/agent-feature-flags",
        headers=headers,
        json={"overrides": {"unknown_x": False}},
    )
    assert response.status_code == 400, "未知 flag 键必须被拒绝"

    response = client.patch(
        f"/api/security/workspaces/{workspace_id}/agent-feature-flags",
        headers=headers,
        json={"overrides": {"loop_v2": "yes"}},
    )
    assert response.status_code == 400, "非布尔值必须被拒绝"

    response = client.patch(
        f"/api/security/workspaces/{workspace_id}/agent-feature-flags",
        headers=headers,
        json={"overrides": {"loop_v2": False, "timeline_v2": False}},
    )
    assert response.status_code == 200
    assert response.get_json()["resolved"]["loop_v2"] is False

    response = client.get(
        f"/api/security/workspaces/{workspace_id}/agent-feature-flags",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.get_json()["overrides"] == {"loop_v2": False, "timeline_v2": False}

    response = client.patch(
        f"/api/security/workspaces/{workspace_id}/agent-feature-flags",
        headers=headers,
        json={"overrides": {"loop_v2": None}},
    )
    assert response.status_code == 200
    assert response.get_json()["overrides"] == {"timeline_v2": False}


def test_workspace_flag_endpoint_denies_non_admin(agent_api_app):
    user_id, workspace_id = make_user(agent_api_app, "flagowner2", "flagowner2@t")
    outsider_id, _ = make_user(agent_api_app, "flagviewer", "flagviewer@t")
    client = agent_api_app.test_client()
    response = client.patch(
        f"/api/security/workspaces/{workspace_id}/agent-feature-flags",
        headers=auth_headers(agent_api_app, outsider_id),
        json={"overrides": {"loop_v2": True}},
    )
    assert response.status_code == 403, "非管理员不能修改 flag"
    response = client.get(
        f"/api/security/workspaces/{workspace_id}/agent-feature-flags",
        headers=auth_headers(agent_api_app, outsider_id),
    )
    assert response.status_code == 403, "非管理员不能读取 flag 覆盖"


def test_run_payload_contains_feature_flags(agent_api_app, tmp_path):
    from test_agent_run_api import make_project_and_snapshot

    user_id, workspace_id = make_user(agent_api_app, "flagpayload", "flagpayload@t")
    project_id, _ = make_project_and_snapshot(
        agent_api_app, tmp_path, user_id, workspace_id
    )
    with agent_api_app.app_context():
        run = AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=1,
            created_by=user_id,
            goal_text="payload flag",
            mode="baseline",
            status=AgentRunStatus.COMPLETED.value,
        )
        db.session.add(run)
        db.session.commit()
        run_id = run.id
    client = agent_api_app.test_client()
    response = client.get(
        f"/api/security/agent-runs/{run_id}",
        headers=auth_headers(agent_api_app, user_id),
    )
    assert response.status_code == 200
    flags = response.get_json().get("feature_flags")
    assert isinstance(flags, dict)
    assert set(flags) == {"loop_v2", "event_schema_v2", "timeline_v2"}
