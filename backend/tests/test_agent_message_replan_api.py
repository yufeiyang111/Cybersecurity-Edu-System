# -*- coding: utf-8 -*-
"""A5 API 测试：运行中消息追加（方向 replan）、计划版本列表、决策时间线。"""
from __future__ import annotations

from flask_jwt_extended import create_access_token

from app import db
from app.models.agent_runtime import (
    AgentDecisionRecord,
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
)
from app.models.conversation import (
    AgentConversation,
    AgentConversationMessage,
    AgentTurn,
    ConversationStatus,
)
from app.models.security import ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.security_agent.conversation_service import ConversationService


def _make_user(application, username="bob", role="owner"):
    with application.app_context():
        user = User(username=username, email=f"{username}@t", password_hash="x")
        db.session.add(user)
        db.session.flush()
        workspace = Workspace(name=f"ws-{username}", slug=f"ws-{username}")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role)
        )
        db.session.commit()
        return user.id, workspace.id


def _auth_headers(application, user_id):
    with application.app_context():
        token = create_access_token(identity=str(user_id), additional_claims={"role": "user"})
    return {"Authorization": f"Bearer {token}"}


def _make_project_snapshot(application, user_id, workspace_id, tmp_path):
    with application.app_context():
        project = SecurityProject(workspace_id=workspace_id, name="demo", created_by=user_id)
        db.session.add(project)
        db.session.flush()
        snapshot_dir = tmp_path / "snap"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "app.py").write_text("import subprocess\n", encoding="utf-8")
        snapshot = ProjectSnapshot(
            project_id=project.id,
            source_type="zip",
            content_sha256="abc",
            storage_path=str(snapshot_dir),
            file_count=1,
            total_bytes=20,
        )
        db.session.add(snapshot)
        db.session.commit()
        return project.id, snapshot.id


def _make_active_run(application, user_id, workspace_id, project_id, snapshot_id, *, status=AgentRunStatus.EXECUTING_TOOLS.value):
    with application.app_context():
        run = AgentRun(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            created_by=user_id,
            goal_text="检查项目安全风险",
            mode=AgentRunMode.BASELINE.value,
            status=status,
            plan_version=1,
        )
        db.session.add(run)
        db.session.flush()
        plan = AgentPlan(run_id=run.id, plan_version=1, planner_source="rule_based_policy")
        db.session.add(plan)
        db.session.flush()
        for key in ("inventory", "baseline_scan"):
            db.session.add(
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key=key,
                    node_type=AgentPlanNodeType.BASELINE_SCAN.value,
                    status=AgentPlanNodeStatus.SUCCEEDED.value,
                    title=key,
                    tool_name="inventory_snapshot",
                )
            )
        conversation = AgentConversation(
            workspace_id=workspace_id,
            project_id=project_id,
            title="会话",
            created_by=user_id,
            status=ConversationStatus.ACTIVE.value,
        )
        db.session.add(conversation)
        db.session.flush()
        turn = AgentTurn(
            conversation_id=conversation.id,
            turn_sequence=1,
            status="active",
        )
        db.session.add(turn)
        db.session.flush()
        turn.run_id = run.id
        db.session.commit()
        return run.id, plan.id, conversation.id


def test_post_message_to_v1_workflow_is_rejected_without_side_effects(agent_api_app, tmp_path):
    """基础工作流不会消费 Control Input，接口必须拒绝而非静默入队。"""
    from app.models.agent_control import AgentControlInput

    user_id, workspace_id = _make_user(agent_api_app)
    project_id, snapshot_id = _make_project_snapshot(agent_api_app, user_id, workspace_id, tmp_path)
    run_id, _, _ = _make_active_run(
        agent_api_app, user_id, workspace_id, project_id, snapshot_id
    )
    headers = _auth_headers(agent_api_app, user_id)
    with agent_api_app.app_context():
        client = agent_api_app.test_client()
        response = client.post(
            f"/api/security/agent-runs/{run_id}/messages",
            headers=headers,
            json={
                "content": "重点检查鉴权和登录逻辑",
                "client_message_id": "msg-replan-0001",
            },
        )
        assert response.status_code == 409
        data = response.get_json()
        assert data["error_code"] == "AGENT_DYNAMIC_CONTROL_UNAVAILABLE"
        assert AgentConversationMessage.query.filter_by(
            client_message_id="msg-replan-0001"
        ).count() == 0
        assert AgentControlInput.query.filter_by(
            run_id=run_id, client_request_id="msg-replan-0001"
        ).count() == 0
        run = db.session.get(AgentRun, run_id)
        assert run.plan_version == 1
        assert run.replan_count == 0
        assert AgentDecisionRecord.query.filter_by(run_id=run_id).count() == 0


def test_post_message_to_v2_agent_run_enqueues_control_input(agent_api_app, tmp_path):
    """V2 Loop 运行中追加消息只入队 Control Input，不直接创建新计划版本。"""
    from app.models.agent_control import AgentControlInput

    agent_api_app.config["AGENT_LOOP_V2_ENABLED"] = True
    user_id, workspace_id = _make_user(agent_api_app, username="v2-bob")
    project_id, snapshot_id = _make_project_snapshot(agent_api_app, user_id, workspace_id, tmp_path)
    run_id, _, _ = _make_active_run(
        agent_api_app, user_id, workspace_id, project_id, snapshot_id
    )
    headers = _auth_headers(agent_api_app, user_id)
    with agent_api_app.app_context():
        client = agent_api_app.test_client()
        response = client.post(
            f"/api/security/agent-runs/{run_id}/messages",
            headers=headers,
            json={
                "content": "重点检查鉴权和登录逻辑",
                "client_message_id": "msg-replan-v2-0001",
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["replayed"] is False
        assert data["control_input"]["input_type"] == "user_message"
        assert data["control_input"]["status"] == "pending"
        assert data["plan_version"] == 1, "HTTP 线程不得创建新计划版本"
        run = db.session.get(AgentRun, run_id)
        assert run.plan_version == 1
        assert run.replan_count == 0
        assert AgentDecisionRecord.query.filter_by(run_id=run_id).count() == 0
        message = AgentConversationMessage.query.filter_by(
            client_message_id="msg-replan-v2-0001"
        ).one()
        assert message.message_type == "follow_up"
        control = AgentControlInput.query.filter_by(
            run_id=run_id, client_request_id="msg-replan-v2-0001"
        ).one()
        assert control.input_type == "user_message"
        assert control.status == "pending"


def test_post_message_idempotent_retry(agent_api_app, tmp_path):
    agent_api_app.config["AGENT_LOOP_V2_ENABLED"] = True
    user_id, workspace_id = _make_user(agent_api_app)
    project_id, snapshot_id = _make_project_snapshot(agent_api_app, user_id, workspace_id, tmp_path)
    run_id, _, _ = _make_active_run(
        agent_api_app, user_id, workspace_id, project_id, snapshot_id
    )
    headers = _auth_headers(agent_api_app, user_id)
    client = agent_api_app.test_client()
    first = client.post(
        f"/api/security/agent-runs/{run_id}/messages",
        headers=headers,
        json={"content": "看看文件上传", "client_message_id": "msg-replan-0002"},
    )
    assert first.status_code == 201
    retry = client.post(
        f"/api/security/agent-runs/{run_id}/messages",
        headers=headers,
        json={"content": "看看文件上传", "client_message_id": "msg-replan-0002"},
    )
    assert retry.status_code == 200
    assert retry.get_json()["replayed"] is True
    with agent_api_app.app_context():
        from app.models.agent_control import AgentControlInput

        assert AgentControlInput.query.filter_by(
            run_id=run_id, client_request_id="msg-replan-0002"
        ).count() == 1
        assert AgentConversationMessage.query.filter_by(
            client_message_id="msg-replan-0002"
        ).count() == 1


def test_post_message_to_terminal_run_conflicts(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    project_id, snapshot_id = _make_project_snapshot(agent_api_app, user_id, workspace_id, tmp_path)
    run_id, _, _ = _make_active_run(
        agent_api_app,
        user_id,
        workspace_id,
        project_id,
        snapshot_id,
        status=AgentRunStatus.COMPLETED.value,
    )
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().post(
        f"/api/security/agent-runs/{run_id}/messages",
        headers=headers,
        json={"content": "继续检查", "client_message_id": "msg-replan-0003"},
    )
    assert response.status_code == 409
    assert response.get_json()["terminal"] is True


def test_post_message_rejects_transient_status(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app)
    project_id, snapshot_id = _make_project_snapshot(agent_api_app, user_id, workspace_id, tmp_path)
    run_id, _, _ = _make_active_run(
        agent_api_app,
        user_id,
        workspace_id,
        project_id,
        snapshot_id,
        status=AgentRunStatus.EVALUATING_EVIDENCE.value,
    )
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().post(
        f"/api/security/agent-runs/{run_id}/messages",
        headers=headers,
        json={"content": "继续检查", "client_message_id": "msg-replan-0004"},
    )
    assert response.status_code == 409


def test_post_message_requires_membership(agent_api_app, tmp_path):
    user_id, workspace_id = _make_user(agent_api_app, username="owner1")
    project_id, snapshot_id = _make_project_snapshot(agent_api_app, user_id, workspace_id, tmp_path)
    run_id, _, _ = _make_active_run(
        agent_api_app, user_id, workspace_id, project_id, snapshot_id
    )
    outsider_id, _ = _make_user(agent_api_app, username="outsider1")
    headers = _auth_headers(agent_api_app, outsider_id)
    response = agent_api_app.test_client().post(
        f"/api/security/agent-runs/{run_id}/messages",
        headers=headers,
        json={"content": "继续检查", "client_message_id": "msg-replan-0005"},
    )
    assert response.status_code == 403


def test_list_plans_and_decisions(agent_api_app, tmp_path):
    agent_api_app.config["AGENT_LOOP_V2_ENABLED"] = True
    user_id, workspace_id = _make_user(agent_api_app)
    project_id, snapshot_id = _make_project_snapshot(agent_api_app, user_id, workspace_id, tmp_path)
    run_id, _, _ = _make_active_run(
        agent_api_app, user_id, workspace_id, project_id, snapshot_id
    )
    headers = _auth_headers(agent_api_app, user_id)
    client = agent_api_app.test_client()
    client.post(
        f"/api/security/agent-runs/{run_id}/messages",
        headers=headers,
        json={"content": "检查 admin 路由", "client_message_id": "msg-replan-0006"},
    )
    plans = client.get(f"/api/security/agent-runs/{run_id}/plans", headers=headers)
    assert plans.status_code == 200
    items = plans.get_json()["items"]
    assert [plan["plan_version"] for plan in items] == [1], "追加消息不创建新计划版本"
    decisions = client.get(f"/api/security/agent-runs/{run_id}/decisions", headers=headers)
    assert decisions.status_code == 200
    records = decisions.get_json()["items"]
    assert len(records) == 0, "追加消息不写决策记录（未重规划）"


def test_conversation_message_to_v1_workflow_is_rejected_without_side_effects(
    agent_api_app, tmp_path
):
    """活跃基础工作流不能伪装成可追问 Agent，也不能落入半条消息。"""
    from app.models.agent_control import AgentControlInput

    user_id, workspace_id = _make_user(agent_api_app, username="conversation-v1")
    project_id, snapshot_id = _make_project_snapshot(
        agent_api_app, user_id, workspace_id, tmp_path
    )
    run_id, _, conversation_id = _make_active_run(
        agent_api_app, user_id, workspace_id, project_id, snapshot_id
    )
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().post(
        f"/api/security/agent-conversations/{conversation_id}/messages",
        headers=headers,
        json={
            "content": "再重点看看数据库查询",
            "client_message_id": "msg-conv-v1-0001",
            "mode": "baseline",
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error_code"] == "AGENT_DYNAMIC_CONTROL_UNAVAILABLE"
    with agent_api_app.app_context():
        assert AgentConversationMessage.query.filter_by(
            client_message_id="msg-conv-v1-0001"
        ).count() == 0
        assert AgentControlInput.query.filter_by(
            run_id=run_id, client_request_id="msg-conv-v1-0001"
        ).count() == 0
        assert AgentTurn.query.filter_by(conversation_id=conversation_id).count() == 1
        run = db.session.get(AgentRun, run_id)
        assert run.plan_version == 1
        assert run.replan_count == 0

def test_conversation_message_to_v2_agent_run_enqueues_control_input(agent_api_app, tmp_path):
    """V2 会话在活跃 Run 上追加方向，不创建新 Turn 或计划。"""
    agent_api_app.config["AGENT_LOOP_V2_ENABLED"] = True
    user_id, workspace_id = _make_user(agent_api_app)
    project_id, snapshot_id = _make_project_snapshot(agent_api_app, user_id, workspace_id, tmp_path)
    run_id, _, conversation_id = _make_active_run(
        agent_api_app, user_id, workspace_id, project_id, snapshot_id
    )
    headers = _auth_headers(agent_api_app, user_id)
    response = agent_api_app.test_client().post(
        f"/api/security/agent-conversations/{conversation_id}/messages",
        headers=headers,
        json={
            "content": "再重点看看数据库查询",
            "client_message_id": "msg-conv-0001",
            "mode": "baseline",
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["run"]["id"] == run_id, "活跃 Run 存在时不应创建新 Run"
    with agent_api_app.app_context():
        from app.models.agent_control import AgentControlInput

        run = db.session.get(AgentRun, run_id)
        assert run.plan_version == 1, "会话消息不得直接触发重规划"
        assert AgentControlInput.query.filter_by(
            run_id=run_id, client_request_id="msg-conv-0001"
        ).count() == 1
        assert AgentDecisionRecord.query.filter_by(run_id=run_id).count() == 0
        turns = AgentTurn.query.filter_by(conversation_id=conversation_id).all()
        assert len(turns) == 1, "活跃 Run 下追加方向不应创建新 Turn"
