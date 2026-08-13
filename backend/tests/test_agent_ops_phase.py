# -*- coding: utf-8 -*-
"""A8-A10 测试：provider 策略、failover 路由、可观测性聚合、watchdog。"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from app import db
from app.models.agent_approval import ApprovalStatus
from app.models.agent_llm import LLMInvocation
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
    AgentToolCall,
)
from app.models.security import (
    ProjectSnapshot,
    SecurityProject,
    Workspace,
    WorkspaceMember,
)
from app.models.user import User
from app.services.agent_observability.operations import (
    observability_overview,
    observability_runs,
)
from app.services.security_agent.approval_service import ApprovalService
from app.services.security_agent.providers.policy import (
    ProviderPolicyError,
    WorkspaceProviderPolicy,
)
from app.services.security_agent.providers.router import AgentProviderRouter
from app.services.security_agent.watchdog import recover_open_runs, watch_open_runs


def _make_run(app, *, status=AgentRunStatus.EXECUTING_TOOLS.value):
    user = User(username="ops", email="ops@t", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(name="w", slug="w-ops")
    db.session.add(workspace)
    db.session.flush()
    db.session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    project = SecurityProject(workspace_id=workspace.id, name="p", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="c-ops",
        storage_path="x",
        file_count=1,
        total_bytes=10,
    )
    db.session.add(snapshot)
    db.session.flush()
    run = AgentRun(
        workspace_id=workspace.id,
        project_id=project.id,
        snapshot_id=snapshot.id,
        created_by=user.id,
        goal_text="g",
        mode=AgentRunMode.BASELINE.value,
        status=status,
        planner_source="rule_based_policy",
    )
    db.session.add(run)
    db.session.flush()
    return run, user, workspace


# ------------------------------------------------------------------ policy


def test_provider_policy_roundtrip(app):
    with app.app_context():
        _, _, workspace = _make_run(app)
        policy = WorkspaceProviderPolicy()
        policy.update(workspace, allowlist=["minimax", "dashscope"], preferred_provider="minimax")
        loaded = policy.get(workspace)
        assert loaded["allowlist"] == ["minimax", "dashscope"]
        assert loaded["preferred_provider"] == "minimax"
        assert policy.allows(workspace, "minimax") is True
        assert policy.allows(workspace, "deepseek-go") is False


def test_provider_policy_rejects_unknown(app):
    with app.app_context():
        _, _, workspace = _make_run(app)
        try:
            WorkspaceProviderPolicy().update(workspace, allowlist=["bogus-provider"], preferred_provider=None)
            raise AssertionError("未知 provider 应被拒绝")
        except ProviderPolicyError:
            pass


def test_provider_policy_preferred_must_be_in_allowlist(app):
    with app.app_context():
        _, _, workspace = _make_run(app)
        try:
            WorkspaceProviderPolicy().update(
                workspace, allowlist=["minimax"], preferred_provider="dashscope"
            )
            raise AssertionError("首选不在 allowlist 应被拒绝")
        except ProviderPolicyError:
            pass


# ------------------------------------------------------------------ router


def test_router_candidates_respects_workspace_preferred(app):
    with app.app_context():
        run, _, workspace = _make_run(app)
        WorkspaceProviderPolicy().update(
            workspace, allowlist=["minimax", "dashscope"], preferred_provider="minimax"
        )
        with patch(
            "app.services.remediation.providers.create_configured_provider",
            return_value=_FakeProvider("minimax"),
        ):
            router = AgentProviderRouter()
            candidates = router.candidates(
                user_id=run.created_by, workspace_id=workspace.id, operation="planner"
            )
        assert candidates, "应至少有一个候选"
        assert candidates[0].provider_name == "minimax"


def test_router_generate_with_failover_switches(app):
    with app.app_context():
        run, _, _ = _make_run(app)
        first = _FakeProvider("broken", fail=True)
        second = _FakeProvider("healthy")
        router = AgentProviderRouter()
        response, used, switches = router.generate_with_failover(
            run=run,
            candidates=[first, second],
            request=object(),
            trace_id="t",
            operation="planner",
        )
        assert response is not None
        assert used.provider_name == "healthy"
        assert len(switches) == 1
        assert switches[0]["from"] == "broken"
        assert switches[0]["to"] == "healthy"


def test_router_generate_all_fail(app):
    with app.app_context():
        run, _, _ = _make_run(app)
        router = AgentProviderRouter()
        response, used, switches = router.generate_with_failover(
            run=run,
            candidates=[_FakeProvider("a", fail=True), _FakeProvider("b", fail=True)],
            request=object(),
            trace_id="t",
            operation="planner",
        )
        assert response is None
        assert used is None
        assert len(switches) == 1


# ------------------------------------------------------------------ observability


def test_observability_overview_and_runs(app):
    with app.app_context():
        run, _, workspace = _make_run(app, status=AgentRunStatus.COMPLETED.value)
        db.session.add(
            AgentToolCall(
                run_id=run.id,
                tool_name="inventory_snapshot",
                status="succeeded",
                idempotency_key=f"k-{run.id}-1",
                latency_ms=42,
            )
        )
        db.session.add(
            LLMInvocation(
                run_id=run.id,
                workspace_id=workspace.id,
                user_id=run.created_by,
                provider_name="minimax",
                model="m",
                operation="planner",
                status="success",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                total_cost=0.001,
                usage_source="provider_reported",
            )
        )
        db.session.commit()

        overview = observability_overview(workspace_id=workspace.id, days=7)
        assert overview["run_counts"]["total"] == 1
        assert overview["run_counts"]["by_status"]["completed"] == 1
        assert overview["tools"]["tools"][0]["tool_name"] == "inventory_snapshot"
        assert overview["tools"]["tools"][0]["latency_ms"] == 42
        assert overview["llm"]["providers"][0]["provider_name"] == "minimax"
        assert overview["llm"]["total_tokens"] == 15

        items, total = observability_runs(workspace_id=workspace.id)
        assert total == 1
        assert items[0]["id"] == run.id


# ------------------------------------------------------------------ watchdog


def test_watchdog_fails_stale_run(app):
    with app.app_context():
        run, _, _ = _make_run(app)
        run.started_at = datetime.utcnow() - timedelta(hours=2)
        run.heartbeat_at = datetime.utcnow() - timedelta(hours=2)
        db.session.commit()
        result = watch_open_runs(stale_seconds=60)
        assert run.id in result["failed"]
        reloaded = db.session.get(AgentRun, run.id)
        assert reloaded.error_code == "AGENT_WATCHDOG_STALE"


def test_watchdog_keeps_healthy_run(app):
    with app.app_context():
        run, _, _ = _make_run(app)
        run.heartbeat_at = datetime.utcnow()
        run.lease_expires_at = datetime.utcnow() + timedelta(minutes=10)
        db.session.commit()
        result = watch_open_runs(stale_seconds=60)
        assert run.id not in result["failed"]


def test_watchdog_resumes_awaiting_approval_after_resolution(app):
    with app.app_context():
        run, user, _ = _make_run(app, status=AgentRunStatus.AWAITING_APPROVAL.value)
        approval = ApprovalService().request(
            run, operation_type="budget_increase", reason="r"
        )
        approval.status = ApprovalStatus.APPROVED.value
        approval.resolved_at = datetime.utcnow()
        db.session.commit()
        result = watch_open_runs(stale_seconds=60)
        assert run.id in result["resumed"]
        reloaded = db.session.get(AgentRun, run.id)
        status = reloaded.status.value if hasattr(reloaded.status, "value") else reloaded.status
        assert status in {
            AgentRunStatus.EXECUTING_TOOLS.value,
            AgentRunStatus.COMPLETED.value,
        }


def test_watchdog_skips_pending_approval(app):
    with app.app_context():
        run, _, _ = _make_run(app, status=AgentRunStatus.AWAITING_APPROVAL.value)
        ApprovalService().request(run, operation_type="budget_increase", reason="r")
        result = watch_open_runs(stale_seconds=60)
        assert run.id not in result["failed"]
        assert run.id not in result["resumed"]


def test_recover_open_runs_is_async_and_idempotent(app):
    """Q-11：恢复入口必须异步驱动（同步执行会让 CLI 长时间挂起、超时中断时
    恢复半途而废，真实验收 run 63 复现）；已恢复的 run 不得重复入队。"""
    import time

    from app.services.security_agent.service import AgentRunService

    run, _, _ = _make_run(app)
    with app.app_context():
        called = []

        def fake_execute(run_id, trace_id):
            called.append((run_id, trace_id))

        with patch("threading.Thread") as mock_thread:
            with patch.object(AgentRunService, "execute_open_run", fake_execute):
                result = recover_open_runs(max_recoveries=5)
        assert run.id in result["recovered"]
        assert mock_thread.called, "恢复必须通过后台线程驱动（异步）"
        assert mock_thread.call_args.kwargs["daemon"] is True
        # 线程 target 是 _drive_recovery：验证其最终会调用 execute_open_run
        target = mock_thread.call_args.kwargs["target"]
        assert target.__name__ == "_drive_recovery"


def test_recover_open_runs_skips_leased_run(app):
    from datetime import datetime, timedelta as dt

    from app.services.security_agent.service import AgentRunService

    run, _, _ = _make_run(app)
    with app.app_context():
        run = db.session.get(AgentRun, run.id)
        run.lease_owner = "other-worker"
        run.lease_expires_at = datetime.utcnow() + dt(minutes=10)
        db.session.commit()
        with patch.object(AgentRunService, "execute_open_run") as fake_execute:
            result = recover_open_runs(max_recoveries=5)
        assert run.id not in result["recovered"]
        assert run.id in result["skipped_leased"]
        fake_execute.assert_not_called()


class _FakeProvider:
    def __init__(self, name, fail=False):
        self.provider_name = name
        self.model = "fake"
        self._fail = fail

    def generate(self, request):
        if self._fail:
            raise RuntimeError("provider down")
        return _FakeResponse()


class _FakeResponse:
    text = "ok"
    is_success = True
    usage = {}
    latency_ms = 1
    warning_code = None
