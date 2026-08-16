# -*- coding: utf-8 -*-
"""Harness V3 目标化 Deep Review 与预算边界回归测试。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app import db
from app.models.agent_hypothesis import (
    AgentAuditHypothesis,
    AuditHypothesisStatus,
)
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
    AgentRunMode,
    AgentRunStatus,
    AgentStepExecution,
)
from app.models.security import (
    ProjectSnapshot,
    SecurityProject,
    Workspace,
    WorkspaceMember,
)
from app.models.user import User
from app.services.security_agent.event_service import EventService
from app.services.security_agent.harness_v3.budget import (
    apply_v3_default_budget,
    resolve_v3_context_char_budget,
)
from app.services.security_agent.harness_v3.deep_review import (
    TargetedContextBuildError,
    TargetedDeepReviewContextBuilder,
    V3DeepReviewInputError,
    V3DeepReviewInputResolver,
)
from app.services.security_agent.tools.executor import ToolExecutor
from app.services.security_agent.tools.registry import get_tool_registry


_V3_FLAGS = {
    "loop_v2": True,
    "event_schema_v2": True,
    "timeline_v2": True,
    "harness_v3": True,
    "provider_raw_reasoning_stream": False,
}
_REQUIRED_EVIDENCE = ["untrusted_input", "dangerous_sink", "guard_or_absence"]


def _make_v3_run(tmp_path: Path, *, files: dict[str, str] | None = None) -> AgentRun:
    user = User(username="v3-review", email="v3-review@example.test", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(name="v3-review-workspace", slug="v3-review-workspace")
    db.session.add(workspace)
    db.session.flush()
    db.session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    project = SecurityProject(
        workspace_id=workspace.id,
        name="v3-review-project",
        created_by=user.id,
    )
    db.session.add(project)
    db.session.flush()

    root = tmp_path / "v3-snapshot"
    root.mkdir(parents=True, exist_ok=True)
    for file_path, content in (files or {"app.py": "pass\n"}).items():
        destination = root / file_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="v3-targeted-context",
        storage_path=str(root),
        file_count=len(files or {"app.py": "pass\n"}),
        total_bytes=100,
    )
    db.session.add(snapshot)
    db.session.flush()
    run = AgentRun(
        workspace_id=workspace.id,
        project_id=project.id,
        snapshot_id=snapshot.id,
        created_by=user.id,
        goal_text="验证不可信输入是否到达危险执行点",
        mode=AgentRunMode.DEEP_AUDIT.value,
        status=AgentRunStatus.EXECUTING_TOOLS.value,
        feature_flags_snapshot_json=dict(_V3_FLAGS),
    )
    db.session.add(run)
    db.session.flush()
    return run


def _make_hypothesis(
    run: AgentRun,
    *,
    scopes: list[dict] | None = None,
    required_evidence: list[str] | None = None,
) -> AgentAuditHypothesis:
    hypothesis = AgentAuditHypothesis(
        run_id=run.id,
        hypothesis_key="unsafe-exec-flow",
        skill_key="unsafe_execution_deserialization",
        title="不可信输入可能到达危险执行点",
        target_summary="核验请求参数是否在缺少有效防护时传入危险执行接口。",
        priority=90,
        status=AuditHypothesisStatus.QUEUED.value,
        planner_source="rule_based_policy",
        required_evidence_json=required_evidence or list(_REQUIRED_EVIDENCE),
        authorized_scopes_json=scopes
        or [{"file_path": "app.py", "start_line": 10, "end_line": 20}],
        satisfied_evidence_json=[],
        evidence_gaps_json=list(_REQUIRED_EVIDENCE),
    )
    db.session.add(hypothesis)
    db.session.flush()
    return hypothesis


def _v3_payload(hypothesis: AgentAuditHypothesis, **overrides) -> dict:
    payload = {
        "hypothesis_id": hypothesis.id,
        "skill_key": hypothesis.skill_key,
        "required_evidence": list(hypothesis.required_evidence_json),
    }
    payload.update(overrides)
    return payload


def _make_deep_review_node(run: AgentRun, payload: dict):
    plan = AgentPlan(run_id=run.id, plan_version=1, planner_source="rule_based_policy")
    db.session.add(plan)
    db.session.flush()
    node = AgentPlanNode(
        plan_id=plan.id,
        node_key="v3_deep_review",
        node_type=AgentPlanNodeType.SEMANTIC_REVIEW.value,
        status=AgentPlanNodeStatus.READY.value,
        title="V3 假设深度审查",
        tool_name="run_deep_review",
        input_json=payload,
    )
    db.session.add(node)
    db.session.flush()
    step = AgentStepExecution(
        plan_node_id=node.id,
        run_id=run.id,
        attempt_number=1,
        status="running",
    )
    db.session.add(step)
    db.session.commit()
    return node, step


def test_v3_resolver_requires_persisted_hypothesis_skill_and_evidence(app, tmp_path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        hypothesis = _make_hypothesis(run)
        resolver = V3DeepReviewInputResolver()

        request = resolver.resolve(run, _v3_payload(hypothesis))

        assert request.hypothesis_id == hypothesis.id
        assert request.focus == hypothesis.target_summary
        assert request.required_evidence == tuple(_REQUIRED_EVIDENCE)

        with pytest.raises(V3DeepReviewInputError, match="证据条件"):
            resolver.resolve(
                run,
                _v3_payload(hypothesis, required_evidence=["untrusted_input"]),
            )
        with pytest.raises(V3DeepReviewInputError, match="自由文本"):
            resolver.resolve(
                run,
                _v3_payload(hypothesis, focus="模型自行扩大到其他文件"),
            )
        with pytest.raises(V3DeepReviewInputError, match="技能"):
            resolver.resolve(
                run,
                _v3_payload(hypothesis, skill_key="injection_dataflow"),
            )


def test_v3_resolver_rejects_corrupted_or_cross_run_scope(app, tmp_path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        hypothesis = _make_hypothesis(
            run,
            scopes=[{"file_path": "../escape.py", "start_line": 1, "end_line": 2}],
        )

        with pytest.raises(V3DeepReviewInputError, match="授权范围"):
            V3DeepReviewInputResolver().resolve(run, _v3_payload(hypothesis))


def test_targeted_context_reads_only_persisted_authorized_window(app, tmp_path):
    lines = [f"line-{index}" for index in range(1, 61)]
    with app.app_context():
        run = _make_v3_run(tmp_path, files={"app.py": "\n".join(lines) + "\n"})
        hypothesis = _make_hypothesis(run)
        request = V3DeepReviewInputResolver().resolve(run, _v3_payload(hypothesis))

        context = TargetedDeepReviewContextBuilder(
            citation_collector=lambda _focus, _limit: ((), ())
        ).build(run, request, max_context_chars=1000)

        assert len(context.files) == 1
        evidence = context.files[0]
        assert evidence.file_path == "app.py"
        assert evidence.start_line == 10
        assert evidence.end_line == 20
        assert evidence.lines[0] == "line-10"
        assert evidence.lines[-1] == "line-20"
        assert "line-9" not in evidence.lines
        assert "line-21" not in evidence.lines
        assert context.total_chars <= 1000


def test_targeted_context_refuses_to_fallback_to_unrelated_file_or_scope(app, tmp_path):
    with app.app_context():
        run = _make_v3_run(tmp_path, files={"app.py": "safe\n"})
        hypothesis = _make_hypothesis(
            run,
            scopes=[{"file_path": "missing.py", "start_line": 1, "end_line": 2}],
        )
        request = V3DeepReviewInputResolver().resolve(run, _v3_payload(hypothesis))

        with pytest.raises(TargetedContextBuildError, match="授权代码证据"):
            TargetedDeepReviewContextBuilder(
                citation_collector=lambda _focus, _limit: ((), ())
            ).build(run, request, max_context_chars=1000)


def test_v3_review_tool_rejects_legacy_free_focus_before_provider_call(app, tmp_path):
    with app.app_context():
        run = _make_v3_run(tmp_path)
        node, step = _make_deep_review_node(
            run,
            {"focus": "自由文本不应触发 V3 Deep Review", "file_hints": ["app.py"]},
        )
        with patch(
            "app.services.security_agent.tools.review_tools.select_provider"
        ) as select_provider:
            result = ToolExecutor(get_tool_registry(), EventService()).execute(
                run,
                node,
                step,
                actor_id=run.created_by,
                trace_id="v3-free-focus",
                input_payload=node.input_json,
            )

        assert result.status == "failed"
        assert "AGENT_V3_DEEP_REVIEW_INPUT_INVALID" in (result.warning_codes or [])
        assert result.error_code == "AGENT_TOOL_FAILED"
        select_provider.assert_not_called()


def test_v3_budget_default_never_overwrites_explicit_user_budget():
    flags = {"harness_v3": True}
    config = {"AGENT_HARNESS_V3_DEEP_AUDIT_DEFAULT_TOKENS": 16000}

    assert apply_v3_default_budget(
        mode="deep_audit",
        budget={"max_total_tokens": 4200},
        feature_flags=flags,
        config=config,
    ) == {"max_total_tokens": 4200}
    assert apply_v3_default_budget(
        mode="deep_audit",
        budget={},
        feature_flags=flags,
        config=config,
    ) == {"max_total_tokens": 16000}
    assert apply_v3_default_budget(
        mode="hybrid",
        budget={},
        feature_flags=flags,
        config=config,
    ) == {}
    assert resolve_v3_context_char_budget(
        explicit_chars=1800,
        config={"AGENT_HARNESS_V3_DEEP_REVIEW_CONTEXT_CHARS": 12000},
    ) == 1800
