# -*- coding: utf-8 -*-
"""Harness V3 漏洞假设只读 API 的授权、分页与脱敏指标测试。"""
from __future__ import annotations

from pathlib import Path

from flask_jwt_extended import create_access_token

from app import db
from app.models.agent_hypothesis import (
    AgentAuditHypothesis,
    AgentAuditHypothesisVerdict,
    AuditHypothesisStatus,
    AuditHypothesisVerdict,
)
from app.models.agent_llm import LLMInvocation
from app.models.agent_runtime import AgentRun, AgentRunMode, AgentRunStatus
from app.models.security import Workspace, WorkspaceMember
from app.models.user import User

from test_agent_harness_v3_deep_review import _make_v3_run

_REQUIRED_EVIDENCE = ["untrusted_input", "dangerous_sink", "guard_or_absence"]


def _headers(application, user_id: int) -> dict[str, str]:
    with application.app_context():
        token = create_access_token(
            identity=str(user_id),
            additional_claims={"role": "user"},
        )
    return {"Authorization": f"Bearer {token}"}


def _add_hypothesis(run, *, key: str, priority: int, status: str):
    hypothesis = AgentAuditHypothesis(
        run_id=run.id,
        hypothesis_key=key,
        skill_key="unsafe_execution_deserialization",
        title=f"候选 {key}",
        target_summary="验证不可信输入是否可到达危险执行接口。",
        priority=priority,
        status=status,
        planner_source="rule_based_policy",
        required_evidence_json=list(_REQUIRED_EVIDENCE),
        authorized_scopes_json=[
            {"file_path": "app.py", "start_line": 10, "end_line": 20}
        ],
        satisfied_evidence_json=(
            list(_REQUIRED_EVIDENCE)
            if status == AuditHypothesisStatus.CONFIRMED.value
            else []
        ),
        evidence_gaps_json=(
            []
            if status == AuditHypothesisStatus.CONFIRMED.value
            else ["缺少受授权的代码位置证据"]
        ),
    )
    db.session.add(hypothesis)
    db.session.flush()
    return hypothesis


def _seed_hypotheses(run) -> tuple[int, int, int]:
    confirmed = _add_hypothesis(
        run,
        key="confirmed-path",
        priority=90,
        status=AuditHypothesisStatus.CONFIRMED.value,
    )
    needs_evidence = _add_hypothesis(
        run,
        key="needs-evidence-path",
        priority=80,
        status=AuditHypothesisStatus.NEEDS_EVIDENCE.value,
    )
    stopped = _add_hypothesis(
        run,
        key="stopped-path",
        priority=70,
        status=AuditHypothesisStatus.STOPPED_FOR_BUDGET.value,
    )
    db.session.add(
        AgentAuditHypothesisVerdict(
            hypothesis_id=confirmed.id,
            verdict_version=1,
            verdict=AuditHypothesisVerdict.CONFIRM_CANDIDATE.value,
            reason_summary="授权范围内已有入口、危险执行点与防护缺口的位置证据。",
            evidence_gaps_json=[],
            next_action_json={
                "action": "record_confirmed_candidate",
                "provider_raw_reasoning": "不得进入详情接口",
                "source_excerpt": "不得进入详情接口",
            },
            critic_version="evidence_critic_v1",
        )
    )
    db.session.add(
        LLMInvocation(
            run_id=run.id,
            workspace_id=run.workspace_id,
            user_id=run.created_by,
            provider_name="fake-provider",
            operation="deep_review",
            status="success",
            total_cost=1.5,
            pricing_version="test-price-v1",
        )
    )
    db.session.commit()
    return confirmed.id, needs_evidence.id, stopped.id


def test_hypothesis_list_uses_server_pagination_and_safe_metrics(agent_api_app, tmp_path: Path):
    with agent_api_app.app_context():
        run = _make_v3_run(tmp_path)
        confirmed_id, needs_evidence_id, _ = _seed_hypotheses(run)
        user_id = run.created_by
        run_id = run.id

    response = agent_api_app.test_client().get(
        f"/api/security/agent-runs/{run_id}/hypotheses?page=1&page_size=2",
        headers=_headers(agent_api_app, user_id),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 3
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert [item["id"] for item in payload["items"]] == [
        confirmed_id,
        needs_evidence_id,
    ]
    assert all("verdicts" not in item for item in payload["items"])
    assert all("provider_raw_reasoning" not in item for item in payload["items"])
    assert all(
        set(item) == {
            "id",
            "hypothesis_key",
            "skill_key",
            "title",
            "target_summary",
            "priority",
            "status",
            "planner_source",
            "required_evidence",
            "authorized_scopes",
            "satisfied_evidence",
            "evidence_gaps",
            "reflection_count",
            "execution_attempt_count",
            "created_at",
            "updated_at",
        }
        for item in payload["items"]
    )
    assert payload["metrics"]["hypothesis_count"] == 3
    assert payload["metrics"]["code_evidence_coverage"] == 0.3333
    assert payload["metrics"]["evidence_insufficient_rate"] == 0.3333
    assert payload["metrics"]["budget_exhaustion_rate"] == 0.3333
    assert payload["metrics"]["deep_review_cost"] == {
        "call_count": 1,
        "cost_known": True,
        "total_cost": 1.5,
        "average_per_hypothesis": 0.5,
    }


def test_hypothesis_detail_contains_only_controlled_verdict_fields(agent_api_app, tmp_path: Path):
    with agent_api_app.app_context():
        run = _make_v3_run(tmp_path)
        confirmed_id, _, _ = _seed_hypotheses(run)
        user_id = run.created_by
        run_id = run.id

    response = agent_api_app.test_client().get(
        f"/api/security/agent-runs/{run_id}/hypotheses/{confirmed_id}",
        headers=_headers(agent_api_app, user_id),
    )

    assert response.status_code == 200
    hypothesis = response.get_json()["hypothesis"]
    verdict = hypothesis["verdicts"][0]
    assert hypothesis["id"] == confirmed_id
    assert hypothesis["authorized_scopes"] == [
        {"file_path": "app.py", "start_line": 10, "end_line": 20}
    ]
    assert set(verdict) == {
        "id",
        "hypothesis_id",
        "verdict_version",
        "verdict",
        "reason_summary",
        "evidence_gaps",
        "next_action",
        "critic_version",
        "created_at",
    }
    assert verdict["verdict"] == "confirm_candidate"
    assert verdict["next_action"] == {"action": "record_confirmed_candidate"}
    serialized = str(hypothesis).lower()
    assert "reasoning_delta" not in serialized
    assert "provider_raw_reasoning" not in serialized
    assert "prompt" not in serialized


def test_hypothesis_detail_hides_cross_run_and_workspace_existence(agent_api_app, tmp_path: Path):
    with agent_api_app.app_context():
        run = _make_v3_run(tmp_path)
        confirmed_id, _, _ = _seed_hypotheses(run)
        owner_id = run.created_by
        other_run = AgentRun(
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            snapshot_id=run.snapshot_id,
            created_by=run.created_by,
            goal_text="用于验证跨 Run 隔离",
            mode=AgentRunMode.DEEP_AUDIT.value,
            status=AgentRunStatus.COMPLETED.value,
            feature_flags_snapshot_json=dict(run.feature_flags_snapshot_json or {}),
        )
        db.session.add(other_run)
        db.session.flush()
        outsider = User(
            username="hypothesis-outsider",
            email="hypothesis-outsider@example.test",
            password_hash="x",
        )
        db.session.add(outsider)
        db.session.flush()
        workspace = Workspace(
            name="hypothesis-outsider-workspace",
            slug="hypothesis-outsider-workspace",
        )
        db.session.add(workspace)
        db.session.flush()
        db.session.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=outsider.id,
                role="owner",
            )
        )
        db.session.commit()
        other_run_id = other_run.id
        outsider_id = outsider.id
        run_id = run.id

    client = agent_api_app.test_client()
    cross_run = client.get(
        f"/api/security/agent-runs/{other_run_id}/hypotheses/{confirmed_id}",
        headers=_headers(agent_api_app, owner_id),
    )
    cross_workspace = client.get(
        f"/api/security/agent-runs/{run_id}/hypotheses",
        headers=_headers(agent_api_app, outsider_id),
    )

    assert cross_run.status_code == 404
    assert cross_workspace.status_code == 403


def test_hypothesis_list_rejects_invalid_pagination(agent_api_app, tmp_path: Path):
    with agent_api_app.app_context():
        run = _make_v3_run(tmp_path)
        _seed_hypotheses(run)
        user_id = run.created_by
        run_id = run.id

    client = agent_api_app.test_client()
    invalid_page = client.get(
        f"/api/security/agent-runs/{run_id}/hypotheses?page=0",
        headers=_headers(agent_api_app, user_id),
    )
    invalid_size = client.get(
        f"/api/security/agent-runs/{run_id}/hypotheses?page_size=101",
        headers=_headers(agent_api_app, user_id),
    )

    assert invalid_page.status_code == 400
    assert invalid_size.status_code == 400
