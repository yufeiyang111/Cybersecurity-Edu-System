# -*- coding: utf-8 -*-
"""A7 测试：审批策略、审批服务（digest/单次/过期/恢复）、观察审核、修复 Diff。"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

from app import db
from app.models.agent_approval import (
    AgentApproval,
    ApprovalOperationType,
    ApprovalStatus,
)
from app.models.agent_review import AgentObservation, ObservationStatus
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
)
from app.models.security import (
    ProjectSnapshot,
    ScanTask,
    SecurityFinding,
    SecurityProject,
    Workspace,
    WorkspaceMember,
)
from app.models.user import User
from app.services.security_agent.approval_policy import can_resolve, requires_approval
from app.services.security_agent.approval_service import (
    ApprovalConflictError,
    ApprovalError,
    ApprovalExpiredError,
    ApprovalService,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.observation_service import (
    ObservationReviewError,
    ObservationService,
)


def _make_run(app, *, budget_exhausted=False):
    user = User(username="ap", email="ap@t", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(name="w", slug="w-ap")
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
        content_sha256="c-ap",
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
        status=AgentRunStatus.AWAITING_APPROVAL.value,
        planner_source="rule_based_policy",
        max_llm_calls=1,
        max_estimated_cost=0.5,
    )
    db.session.add(run)
    db.session.flush()
    plan = AgentPlan(run_id=run.id, plan_version=1, planner_source="rule_based_policy")
    db.session.add(plan)
    db.session.flush()
    db.session.add(
        AgentPlanNode(
            plan_id=plan.id,
            node_key="inventory",
            node_type=AgentPlanNodeType.INVENTORY.value,
            status=AgentPlanNodeStatus.SUCCEEDED.value,
            title="i",
            tool_name="inventory_snapshot",
        )
    )
    db.session.add(
        AgentPlanNode(
            plan_id=plan.id,
            node_key="report",
            node_type=AgentPlanNodeType.REPORT_GENERATION.value,
            status=AgentPlanNodeStatus.PENDING.value,
            title="r",
            tool_name="finalize_agent_report",
        )
    )
    db.session.commit()
    return run, user, workspace


def _make_observation(app, run, *, status=ObservationStatus.UNVERIFIED.value):
    observation = AgentObservation(
        run_id=run.id,
        title="XSS 风险",
        status=status,
        confidence="medium",
        summary="输入未转义",
    )
    db.session.add(observation)
    db.session.commit()
    return observation


# ------------------------------------------------------------------ policy


def test_requires_approval_logic():
    assert requires_approval(budget_exhausted=True, plan_incomplete=True) is True
    assert requires_approval(budget_exhausted=True, plan_incomplete=False) is False
    assert requires_approval(budget_exhausted=False, plan_incomplete=True) is False


def test_can_resolve_roles():
    class FakeApproval:
        risk_level = "medium"

    class FakeHigh:
        risk_level = "high"

    assert can_resolve(FakeApproval(), "owner") is True
    assert can_resolve(FakeApproval(), "admin") is True
    assert can_resolve(FakeApproval(), "analyst") is False
    assert can_resolve(FakeHigh(), "analyst") is False


# ------------------------------------------------------------------ approval service


def test_approval_request_and_resolve_approved(app):
    with app.app_context():
        run, user, workspace = _make_run(app)
        service = ApprovalService()
        approval = service.request(
            run,
            operation_type=ApprovalOperationType.BUDGET_INCREASE.value,
            reason="预算超限",
            affected_scope={"reached_codes": ["AGENT_BUDGET_EXHAUSTED"]},
            proposed={"budget": {"max_llm_calls": 4, "max_estimated_cost": 1.0}},
            requester_id=user.id,
        )
        assert approval.status == ApprovalStatus.PENDING.value
        assert approval.operation_digest

        resolved = service.resolve(
            run,
            approval.id,
            decision="approved",
            comment="同意追加",
            resolver_id=user.id,
            resolver_role="owner",
        )
        assert resolved.status == ApprovalStatus.APPROVED.value
        assert run.max_llm_calls == 4
        assert float(run.max_estimated_cost) == 1.0
        status = run.status.value if hasattr(run.status, "value") else run.status
        assert status in {
            AgentRunStatus.EXECUTING_TOOLS.value,
            AgentRunStatus.COMPLETED.value,
        }, "批准后应恢复执行（同步模式下可能直接完成）"


def test_approval_request_idempotent_by_digest(app):
    with app.app_context():
        run, user, _ = _make_run(app)
        service = ApprovalService()
        first = service.request(
            run, operation_type="budget_increase", reason="r", proposed={"budget": {"max_llm_calls": 2}}
        )
        second = service.request(
            run, operation_type="budget_increase", reason="r", proposed={"budget": {"max_llm_calls": 2}}
        )
        assert first.id == second.id
        assert AgentApproval.query.filter_by(run_id=run.id).count() == 1


def test_approval_resolve_single_use(app):
    with app.app_context():
        run, user, _ = _make_run(app)
        service = ApprovalService()
        approval = service.request(run, operation_type="budget_increase", reason="r")
        service.resolve(
            run, approval.id, decision="rejected", comment="", resolver_id=user.id, resolver_role="owner"
        )
        try:
            service.resolve(
                run, approval.id, decision="approved", comment="", resolver_id=user.id, resolver_role="owner"
            )
            raise AssertionError("重复决策应被拒绝")
        except ApprovalConflictError:
            pass


def test_approval_resolve_expired(app):
    with app.app_context():
        run, user, _ = _make_run(app)
        service = ApprovalService()
        approval = service.request(run, operation_type="budget_increase", reason="r")
        approval.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()
        try:
            service.resolve(
                run, approval.id, decision="approved", comment="", resolver_id=user.id, resolver_role="owner"
            )
            raise AssertionError("过期审批应被拒绝")
        except ApprovalExpiredError:
            pass
        reloaded = db.session.get(AgentApproval, approval.id)
        assert reloaded.status == ApprovalStatus.EXPIRED.value


def test_approval_resolve_role_denied(app):
    with app.app_context():
        run, user, _ = _make_run(app)
        service = ApprovalService()
        approval = service.request(run, operation_type="budget_increase", reason="r")
        try:
            service.resolve(
                run, approval.id, decision="approved", comment="", resolver_id=user.id, resolver_role="analyst"
            )
            raise AssertionError("analyst 不应能批准 medium 审批")
        except ApprovalError:
            pass


def test_approval_reject_marks_run_partial(app):
    with app.app_context():
        run, user, _ = _make_run(app)
        service = ApprovalService()
        approval = service.request(run, operation_type="budget_increase", reason="r")
        service.resolve(
            run, approval.id, decision="rejected", comment="不可接受", resolver_id=user.id, resolver_role="owner"
        )
        status = run.status.value if hasattr(run.status, "value") else run.status
        assert status == AgentRunStatus.PARTIAL.value


# ------------------------------------------------------------------ observation review


def test_observation_review_confirm(app):
    with app.app_context():
        run, user, _ = _make_run(app)
        observation = _make_observation(app, run)
        reviewed = ObservationService().review(
            run, observation, decision="confirmed", comment="证据充分", actor_id=user.id
        )
        assert reviewed.status == ObservationStatus.CONFIRMED.value
        detail = reviewed.detail_json or {}
        assert detail["review_comment"] == "证据充分"


def test_observation_review_terminal_immutable(app):
    with app.app_context():
        run, user, _ = _make_run(app)
        observation = _make_observation(app, run, status=ObservationStatus.CONFIRMED.value)
        try:
            ObservationService().review(
                run, observation, decision="rejected", actor_id=user.id
            )
            raise AssertionError("已确认结论不可再变更")
        except ObservationReviewError:
            pass


# ------------------------------------------------------------------ remediation diff


def test_remediation_diff_only_for_confirmed(app):
    with app.app_context():
        run, user, _ = _make_run(app)
        observation = _make_observation(app, run, status=ObservationStatus.UNVERIFIED.value)
        try:
            ObservationService().generate_remediation_diff(run, observation, actor_id=user.id)
            raise AssertionError("未确认观察不应生成修复 Diff")
        except ObservationReviewError:
            pass


def test_remediation_diff_generates_restricted_diff(app, tmp_path):
    with app.app_context():
        run, user, workspace = _make_run(app)
        root = tmp_path / "snap"
        root.mkdir(parents=True, exist_ok=True)
        (root / "app.py").write_text("value = request.args.get('x')\n", encoding="utf-8")
        snapshot = db.session.get(ProjectSnapshot, run.snapshot_id)
        snapshot.storage_path = str(root)
        db.session.commit()

        observation = _make_observation(app, run, status=ObservationStatus.CONFIRMED.value)
        from app.models.agent_review import AgentObservationLocation

        db.session.add(
            AgentObservationLocation(
                observation_id=observation.id,
                file_path="app.py",
                start_line=1,
                end_line=1,
                role="sink",
            )
        )
        db.session.commit()

        diff_text = (
            "--- a/app.py\n+++ b/app.py\n"
            "@@ -1,1 +1,2 @@\n value = request.args.get('x')\n"
            "+value = escape(request.args.get('x'))\n"
        )

        class FakeResponse:
            text = diff_text
            is_success = True
            usage = {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12}
            latency_ms = 9
            warning_code = None

        class FakeProvider:
            provider_name = "fake"
            model = "fake"

            def generate(self, request):
                return FakeResponse()

        with patch(
            "app.services.llm.provider_selector.select_provider",
            return_value=FakeProvider(),
        ):
            result = ObservationService().generate_remediation_diff(
                run, observation, actor_id=user.id
            )
        assert "+value = escape" in result["diff"]
        assert result["file_paths"] == ["app.py"]
        detail = db.session.get(AgentObservation, observation.id).detail_json
        assert detail["remediation_diff"]["file_paths"] == ["app.py"]


def test_remediation_diff_rejects_out_of_scope_files(app, tmp_path):
    with app.app_context():
        run, user, _ = _make_run(app)
        observation = _make_observation(app, run, status=ObservationStatus.CONFIRMED.value)
        from app.models.agent_review import AgentObservationLocation

        db.session.add(
            AgentObservationLocation(
                observation_id=observation.id,
                file_path="app.py",
                start_line=1,
                role="sink",
            )
        )
        db.session.commit()

        diff_text = (
            "--- a/other.py\n+++ b/other.py\n@@ -1,1 +1,2 @@\n-x\n+x\n"
        )

        class FakeResponse:
            text = diff_text
            is_success = True
            usage = {}
            latency_ms = 1
            warning_code = None

        class FakeProvider:
            provider_name = "fake"
            model = "fake"

            def generate(self, request):
                return FakeResponse()

        with patch(
            "app.services.llm.provider_selector.select_provider",
            return_value=FakeProvider(),
        ):
            try:
                ObservationService().generate_remediation_diff(
                    run, observation, actor_id=user.id
                )
                raise AssertionError("范围外文件应被拒绝")
            except ObservationReviewError:
                pass
