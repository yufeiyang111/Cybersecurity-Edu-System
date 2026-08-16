# -*- coding: utf-8 -*-
"""T15.1 审计技能、漏洞假设与 V3 开关的边界回归测试。"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app import db
from app.models.agent_hypothesis import (
    AgentAuditHypothesis,
    AgentAuditHypothesisVerdict,
    AuditHypothesisStatus,
    AuditHypothesisVerdict,
)
from app.models.agent_runtime import AgentRun, AgentRunStatus
from app.models.security import Workspace
from app.services.security_agent.audit_skills import AuditSkillCatalog
from app.services.security_agent.feature_flags import AgentFeatureFlags
from app.services.security_agent.hypotheses.contracts import (
    AuditHypothesisDraft,
    CodeLocationScope,
)
from app.services.security_agent.hypotheses.validator import (
    HypothesisValidationError,
    HypothesisValidator,
)


def _workspace(name: str, overrides: dict | None = None) -> Workspace:
    workspace = Workspace(
        name=name,
        slug=name,
        agent_feature_flags=overrides,
    )
    db.session.add(workspace)
    db.session.flush()
    return workspace


def _run(workspace_id: int) -> AgentRun:
    run = AgentRun(
        workspace_id=workspace_id,
        project_id=1,
        snapshot_id=1,
        created_by=1,
        goal_text="验证漏洞假设契约",
        mode="hybrid",
        status=AgentRunStatus.EXECUTING_TOOLS.value,
    )
    db.session.add(run)
    db.session.flush()
    return run


def _scope(
    file_path: str = "app/routes/auth.py",
    start_line: int = 10,
    end_line: int = 42,
) -> CodeLocationScope:
    return CodeLocationScope(
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
    )


def _valid_draft(
    *,
    hypothesis_key: str = "h-001",
    scopes: tuple[CodeLocationScope, ...] | None = None,
    required_evidence: tuple[str, ...] | None = None,
) -> AuditHypothesisDraft:
    return AuditHypothesisDraft(
        hypothesis_key=hypothesis_key,
        skill_key="unsafe_execution_deserialization",
        title="不可信输入可能流向危险执行点",
        target_summary="验证不可信输入是否在缺少明确防护时到达危险执行接口。",
        priority=80,
        required_evidence=required_evidence
        or ("untrusted_input", "dangerous_sink", "guard_or_absence"),
        authorized_scopes=scopes or (_scope(),),
        planner_source="rule_based_policy",
    )


def test_catalog_is_fixed_and_does_not_allow_runtime_registration():
    catalog = AuditSkillCatalog()

    assert catalog.keys() == (
        "authorization_boundary",
        "injection_dataflow",
        "unsafe_execution_deserialization",
        "untrusted_file_network",
        "unsafe_runtime_configuration",
    )
    assert catalog.get("unknown_prompt_skill") is None
    assert catalog.get("unsafe_execution_deserialization") is not None

    skill = catalog.require("unsafe_execution_deserialization")
    with pytest.raises(FrozenInstanceError):
        skill.key = "user_supplied_skill"


def test_validator_accepts_registered_skill_with_authorized_evidence_scope():
    draft = _valid_draft()

    validated = HypothesisValidator().validate_batch(
        (draft,),
        allowed_scopes=(_scope(),),
    )

    assert validated == (draft,)


@pytest.mark.parametrize(
    ("draft", "allowed_scopes", "message"),
    [
        (
            AuditHypothesisDraft(
                hypothesis_key="h-001",
                skill_key="unknown_prompt_skill",
                title="未知技能",
                target_summary="不得动态注册任意技能。",
                priority=50,
                required_evidence=("untrusted_input",),
                authorized_scopes=(_scope(),),
                planner_source="llm_live",
            ),
            (_scope(),),
            "未注册",
        ),
        (
            _valid_draft(required_evidence=("untrusted_input",)),
            (_scope(),),
            "缺少",
        ),
        (
            _valid_draft(scopes=(_scope("../outside.py"),)),
            (_scope(),),
            "路径",
        ),
        (
            _valid_draft(scopes=(_scope("app/routes/auth.py", 1, 80),)),
            (_scope(),),
            "授权范围",
        ),
    ],
)
def test_validator_rejects_untrusted_or_unverifiable_hypotheses(
    draft: AuditHypothesisDraft,
    allowed_scopes: tuple[CodeLocationScope, ...],
    message: str,
):
    with pytest.raises(HypothesisValidationError, match=message):
        HypothesisValidator().validate_batch((draft,), allowed_scopes=allowed_scopes)


def test_validator_rejects_more_than_configured_candidate_limit():
    drafts = tuple(_valid_draft(hypothesis_key=f"h-{index:03d}") for index in range(1, 5))

    with pytest.raises(HypothesisValidationError, match="最多"):
        HypothesisValidator(max_hypotheses=3).validate_batch(
            drafts,
            allowed_scopes=(_scope(),),
        )


def test_v3_flags_are_safe_by_default_and_old_run_snapshot_stays_v3_off(app):
    with app.app_context():
        app.config["AGENT_HARNESS_V3_ENABLED"] = True
        app.config["AGENT_PROVIDER_RAW_REASONING_STREAM_ENABLED"] = True
        workspace = _workspace("v3-flag-snapshot")
        run = _run(workspace.id)
        run.feature_flags_snapshot_json = {
            "loop_v2": True,
            "event_schema_v2": True,
            "timeline_v2": True,
        }
        db.session.flush()

        flags = AgentFeatureFlags().for_run(run)

        assert flags.loop_v2 is True
        assert flags.harness_v3 is False
        assert flags.provider_raw_reasoning_stream is False


def test_workspace_owner_flags_can_enable_v3_and_raw_reasoning_snapshot(app):
    with app.app_context():
        workspace = _workspace(
            "v3-flags-enabled",
            {
                "loop_v2": True,
                "harness_v3": True,
                "provider_raw_reasoning_stream": True,
            },
        )

        flags = AgentFeatureFlags().for_workspace(workspace.id)

        assert flags.loop_v2 is True
        assert flags.harness_v3 is True
        assert flags.provider_raw_reasoning_stream is True


def test_hypothesis_and_verdict_persist_only_structured_audit_facts(app):
    with app.app_context():
        workspace = _workspace("hypothesis-models")
        run = _run(workspace.id)
        hypothesis = AgentAuditHypothesis(
            run_id=run.id,
            hypothesis_key="h-001",
            skill_key="unsafe_execution_deserialization",
            title="不可信输入到危险执行点",
            target_summary="验证输入到执行接口之间是否存在有效防护。",
            priority=80,
            status=AuditHypothesisStatus.NEEDS_EVIDENCE.value,
            planner_source="rule_based_policy",
            required_evidence_json=["untrusted_input", "dangerous_sink", "guard_or_absence"],
            authorized_scopes_json=[_scope().to_dict()],
            evidence_gaps_json=["缺少危险调用点位置"],
        )
        db.session.add(hypothesis)
        db.session.flush()
        verdict = AgentAuditHypothesisVerdict(
            hypothesis_id=hypothesis.id,
            verdict_version=1,
            verdict=AuditHypothesisVerdict.NEEDS_MORE_EVIDENCE.value,
            reason_summary="尚未获得可验证的危险调用点位置。",
            evidence_gaps_json=["缺少危险调用点位置"],
            next_action_json={"kind": "request_evidence"},
            critic_version="v3-test",
        )
        db.session.add(verdict)
        db.session.commit()

        payload = hypothesis.to_dict(include_verdicts=True)

        assert payload["skill_key"] == "unsafe_execution_deserialization"
        assert payload["status"] == "needs_evidence"
        assert payload["verdicts"][0]["verdict"] == "needs_more_evidence"
        assert "raw_reasoning" not in payload
        assert "prompt" not in payload
        assert "source_code" not in payload

def test_v3_environment_flags_are_documented_without_reading_local_env():
    backend_root = Path(__file__).resolve().parents[1]
    example = (backend_root / ".env.example").read_text(encoding="utf-8")

    assert "AGENT_HARNESS_V3_ENABLED=false" in example
    assert "AGENT_PROVIDER_RAW_REASONING_STREAM_ENABLED=false" in example