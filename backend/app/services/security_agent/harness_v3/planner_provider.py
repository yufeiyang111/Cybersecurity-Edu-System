# -*- coding: utf-8 -*-
"""Harness V3 假设规划的 Provider 调用与受限 JSON 适配。"""
from __future__ import annotations

from app import db
from app.models.agent_runtime import AgentRun
from app.services.llm.contracts import LLMRequest
from app.services.llm.provider_selector import resolve_provider_max_tokens
from app.services.security_agent.audit_skills import AuditSkill, AuditSkillCatalog
from app.services.security_agent.hypotheses.contracts import AuditHypothesisDraft
from app.services.security_agent.hypotheses.validator import (
    HypothesisValidationError,
    HypothesisValidator,
)
from app.services.security_agent.llm_invocation import (
    USAGE_SOURCE_PROVIDER_REPORTED,
    record_invocation,
)
from app.services.security_agent.prompt_templates.hypothesis_planner_v1 import (
    PROMPT_TEMPLATE_VERSION,
    build_hypothesis_planner_prompt,
    parse_hypothesis_plan,
    prompt_digest,
)

from .planner_signals import (
    FindingSignal,
    max_hypotheses,
    make_hypothesis_draft,
    normalize_priority,
    scopes_from_indices,
)

HYPOTHESIS_PLANNER_OPERATION = "hypothesis_planner"


class ProviderHypothesisDraftBuilder:
    """把 Provider 受限 JSON 转成经验证的无源码漏洞假设草稿。"""

    def __init__(
        self,
        *,
        catalog: AuditSkillCatalog,
        validator: HypothesisValidator,
    ) -> None:
        self._catalog = catalog
        self._validator = validator

    def build(
        self,
        run: AgentRun,
        *,
        provider: object,
        skills: tuple[AuditSkill, ...],
        signals: tuple[FindingSignal, ...],
    ) -> tuple[AuditHypothesisDraft, ...]:
        """调用 Provider，并在持久化前逐条校验其技能与授权范围选择。"""
        prompt = build_hypothesis_planner_prompt(
            skills=skills,
            finding_signals=signals,
            max_hypotheses=max_hypotheses(),
        )
        request = LLMRequest(
            prompt=prompt["user_prompt"],
            system_prompt=prompt["system_prompt"],
            temperature=0.0,
            max_tokens=resolve_provider_max_tokens(provider, prompt["max_tokens"]),
        )
        response = provider.generate(request)
        self._record_invocation(
            run,
            provider,
            response,
            prompt["user_prompt"],
        )
        if response is None or not bool(getattr(response, "is_success", False)):
            raise RuntimeError("Provider 未返回成功规划结果")

        parsed = parse_hypothesis_plan(str(getattr(response, "text", "") or ""))
        candidates = parsed.get("hypotheses")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("hypotheses 必须是非空数组")

        allowed_skill_keys = {skill.key for skill in skills}
        drafts: list[AuditHypothesisDraft] = []
        seen_skills: set[str] = set()
        for candidate in candidates:
            if len(drafts) >= max_hypotheses():
                break
            if not isinstance(candidate, dict):
                raise ValueError("hypotheses 子项必须是对象")
            skill_key = str(candidate.get("skill_key") or "").strip()
            if skill_key not in allowed_skill_keys or skill_key in seen_skills:
                raise HypothesisValidationError("Provider 选择了未授权或重复的审计技能")

            scopes = scopes_from_indices(candidate.get("scope_indices"), signals)
            draft = make_hypothesis_draft(
                run=run,
                skill=self._catalog.require(skill_key),
                scopes=scopes,
                priority=normalize_priority(candidate.get("priority")),
                planner_source="llm_live",
            )
            self._validator.validate_batch(
                (draft,),
                allowed_scopes=scopes,
            )
            drafts.append(draft)
            seen_skills.add(skill_key)
        return tuple(drafts)

    @staticmethod
    def _record_invocation(
        run: AgentRun,
        provider: object,
        response: object | None,
        prompt: str,
    ) -> None:
        """只持久化用量和摘要哈希，绝不写入 Prompt 或 Provider 原文。"""
        usage = getattr(response, "usage", None) or {}
        text = str(getattr(response, "text", "") or "")
        record_invocation(
            run,
            provider=provider,
            operation=HYPOTHESIS_PLANNER_OPERATION,
            status=(
                "success"
                if response is not None and getattr(response, "is_success", False)
                else "failed"
            ),
            warning_code=getattr(response, "warning_code", None),
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            cached_input_tokens=int(usage.get("cached_tokens") or 0),
            reasoning_tokens=int(usage.get("reasoning_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            usage_source=(
                USAGE_SOURCE_PROVIDER_REPORTED
                if usage
                else "estimated"
            ),
            latency_ms=getattr(response, "latency_ms", None),
            input_digest=prompt_digest(prompt),
            output_digest=prompt_digest(text) if text else None,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
        )
        db.session.commit()
