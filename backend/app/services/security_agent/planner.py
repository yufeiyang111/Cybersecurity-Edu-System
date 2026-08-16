# -*- coding: utf-8 -*-
"""Planner: LLM-generated PlanEnvelope with rule-based fallback (never fake).

Decision rule:
- Provider available + budget not exhausted -> call the LLM planner, validate,
  repair once, then persist the plan as planner_source=llm_live.
- No provider / budget exhausted / parse or validation failure after repair ->
  persist the explicit rule-based baseline plan (planner_source=rule_based_policy)
  with an honest fallback_reason; never masquerade as LLM output.
"""
from __future__ import annotations

import logging

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanEdge,
    AgentPlanEdgeType,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentPlanNodeType,
    AgentRun,
)
from app.services.agent_observability import AgentLogger
from app.services.llm.contracts import LLMRequest, LLMResponse
from app.services.llm.provider_selector import resolve_provider_max_tokens, select_provider
from app.services.security_agent.budget import budget_status
from app.services.security_agent.contracts import (
    EVENT_BUDGET_UPDATED,
    EVENT_WARNING_RAISED,
    PLANNER_RULE_BASED,
    PLANNER_LLM_LIVE,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.intent_parser import parse_intent
from app.services.security_agent.llm_invocation import (
    USAGE_SOURCE_PROVIDER_REPORTED,
    record_invocation,
)
from app.services.security_agent.plan_validator import PlanValidationError, validate_envelope
from app.services.security_agent.prompt_templates.planner_v1 import (
    PROMPT_TEMPLATE_VERSION,
    build_user_prompt,
    parse_plan_envelope,
    prompt_digest,
)
from app.services.security_agent.timeline.contracts import (
    EVENT_PLAN_CREATED,
)
from app.services.security_agent.timeline.event_writer import EventWriter
from app.services.security_agent.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

PLANNER_OPERATION = "planner"
MAX_REPAIR_ATTEMPTS = 2


class PlanPlanner:
    """Builds the durable AgentPlan for a run (LLM plan with honest fallback)."""

    def __init__(self, events: EventService) -> None:
        self._events = events
        self._writer = EventWriter()
        self._agent_log = AgentLogger()

    # ------------------------------------------------------------------ public

    def generate_plan(self, run: AgentRun, *, trace_id: str) -> AgentPlan:
        """Return a persisted AgentPlan; always falls back to the rule plan."""
        status = budget_status(run)
        if status["exhausted"]:
            self._emit_budget(run, status, trace_id)
            return self._build_plan(
                run,
                trace_id,
                planner_source=PLANNER_RULE_BASED,
                fallback_reason="运行预算已耗尽，LLM 规划被阻断",
            )

        provider = select_provider(user_id=run.created_by, operation=PLANNER_OPERATION)
        if provider is None:
            return self._build_plan(
                run,
                trace_id,
                planner_source=PLANNER_RULE_BASED,
                fallback_reason="未配置 LLM Provider，使用本地策略计划",
            )

        envelope = self._llm_plan(run, provider, trace_id)

        if envelope is None:
            return self._build_plan(
                run,
                trace_id,
                planner_source=PLANNER_RULE_BASED,
                fallback_reason="LLM 规划失败或校验未通过，使用本地策略计划",
            )
        return self._build_plan(
            run,
            trace_id,
            planner_source=PLANNER_LLM_LIVE,
            envelope=envelope,
        )

    # ------------------------------------------------------------------ llm

    def _llm_plan(self, run: AgentRun, provider: object, trace_id: str) -> dict | None:
        """One or two attempts at an LLM plan; returns a validated envelope or None."""
        intent = parse_intent(run.goal_text)
        snapshot_summary = _snapshot_summary(run)
        registry = get_tool_registry()
        tools = [
            {"name": descriptor.name, "description": descriptor.description}
            for descriptor in registry.descriptors()
        ]
        budget = _budget_payload(run)
        base_prompt = build_user_prompt(
            goal=run.goal_text,
            intent=intent,
            snapshot_summary=snapshot_summary,
            available_tools=tools,
            budget=budget,
            run_mode=_run_mode(run),
        )
        last_error = ""
        for attempt in range(MAX_REPAIR_ATTEMPTS):
            if attempt > 0:
                repair_prompt = (
                    f"{base_prompt}\n\n上一次规划未通过校验，失败原因：{last_error}。"
                    "请修正后重新输出 PlanEnvelope JSON。"
                )
            else:
                repair_prompt = base_prompt
            response = self._call_planner(run, provider, repair_prompt, trace_id)
            if response is None:
                return None
            try:
                envelope = parse_plan_envelope(response.text)
                return validate_envelope(
                    envelope,
                    available_tools=registry.names(),
                    tool_allowed_modes={
                        descriptor.name: set(descriptor.allowed_modes)
                        for descriptor in registry.descriptors()
                    },
                    run_mode=_run_mode(run),
                )
            except (ValueError, PlanValidationError) as exc:
                last_error = str(exc)[:500]
                logger.warning(
                    "Agent planner envelope invalid (run_id=%s, attempt=%s, error_type=%s)",
                    run.id,
                    attempt,
                    type(exc).__name__,
                )
                self._agent_log.plan_repair_failed(
                    run,
                    attempt=attempt,
                    reason=str(exc),
                    trace_id=trace_id,
                )
        self._raise_warning(run, "AGENT_PLAN_REPAIR_EXHAUSTED", trace_id)
        return None

    def _call_planner(
        self, run: AgentRun, provider: object, prompt: str, trace_id: str
    ) -> LLMResponse | None:
        """按候选链调用规划 Provider（A8 failover）：首选失败自动切换备用。"""
        from app.services.security_agent.providers.router import AgentProviderRouter

        request = LLMRequest(
            prompt=prompt,
            system_prompt=(
                "你是 CyberGuard 安全 Agent 的计划器。"
                "只输出符合要求的 PlanEnvelope JSON。"
            ),
            temperature=0.2,
            max_tokens=resolve_provider_max_tokens(provider, 1500),
        )
        router = AgentProviderRouter(self._events)
        candidates = router.candidates(
            user_id=run.created_by,
            workspace_id=run.workspace_id,
            operation=PLANNER_OPERATION,
        )
        ordered = [provider] + [
            candidate
            for candidate in candidates
            if getattr(candidate, "provider_name", None)
            != getattr(provider, "provider_name", None)
        ]
        response, used, _ = router.generate_with_failover(
            run=run,
            candidates=ordered,
            request=request,
            trace_id=trace_id,
            operation=PLANNER_OPERATION,
        )
        if response is None:
            logger.warning(
                "Agent planner provider chain failed (run_id=%s)",
                run.id,
            )
            record_invocation(
                run,
                provider=provider,
                operation=PLANNER_OPERATION,
                status="failed",
                warning_code="LLM_PROVIDER_REQUEST_FAILED",
                usage_source=USAGE_SOURCE_PROVIDER_REPORTED,
                input_digest=prompt_digest(prompt),
                prompt_template_version=PROMPT_TEMPLATE_VERSION,
            )
            db.session.commit()
            self._agent_log.llm_event(
                "llm.failed",
                run,
                operation=PLANNER_OPERATION,
                provider=getattr(provider, "provider_name", "unknown"),
                model=getattr(provider, "model", None),
                status="failed",
                warning_code="LLM_PROVIDER_REQUEST_FAILED",
                usage_source=USAGE_SOURCE_PROVIDER_REPORTED,
                input_digest=prompt_digest(prompt),
                prompt_template_version=PROMPT_TEMPLATE_VERSION,
                trace_id=trace_id,
            )
            return None
        record_invocation(
            run,
            provider=used,
            operation=PLANNER_OPERATION,
            status="success" if response.is_success else "failed",
            warning_code=response.warning_code,
            input_tokens=int((response.usage or {}).get("prompt_tokens") or 0),
            output_tokens=int((response.usage or {}).get("completion_tokens") or 0),
            cached_input_tokens=int((response.usage or {}).get("cached_tokens") or 0),
            reasoning_tokens=int((response.usage or {}).get("reasoning_tokens") or 0),
            total_tokens=int((response.usage or {}).get("total_tokens") or 0),
            usage_source=USAGE_SOURCE_PROVIDER_REPORTED
            if response.usage
            else "estimated",
            latency_ms=response.latency_ms,
            first_token_latency_ms=None,
            input_digest=prompt_digest(prompt),
            output_digest=prompt_digest(response.text) if response.text else None,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
        )
        db.session.commit()
        self._agent_log.llm_event(
            "llm.completed" if response.is_success else "llm.failed",
            run,
            operation=PLANNER_OPERATION,
            provider=getattr(used, "provider_name", "unknown"),
            model=getattr(used, "model", None),
            status="success" if response.is_success else "failed",
            warning_code=response.warning_code,
            input_tokens=int((response.usage or {}).get("prompt_tokens") or 0),
            output_tokens=int((response.usage or {}).get("completion_tokens") or 0),
            cached_input_tokens=int((response.usage or {}).get("cached_tokens") or 0),
            reasoning_tokens=int((response.usage or {}).get("reasoning_tokens") or 0),
            total_tokens=int((response.usage or {}).get("total_tokens") or 0),
            usage_source=USAGE_SOURCE_PROVIDER_REPORTED if response.usage else "estimated",
            latency_ms=response.latency_ms,
            input_digest=prompt_digest(prompt),
            output_digest=prompt_digest(response.text) if response.text else None,
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
            trace_id=trace_id,
        )
        return response

    # ------------------------------------------------------------------ build

    def _build_plan(
        self,
        run: AgentRun,
        trace_id: str,
        *,
        planner_source: str,
        envelope: dict | None = None,
        fallback_reason: str | None = None,
    ) -> AgentPlan:
        """Persist one plan version from an envelope or the rule-based baseline."""
        plan = AgentPlan(
            run_id=run.id,
            plan_version=run.plan_version + 1,
            planner_source=planner_source,
            objective=(envelope or {}).get("objective") or run.goal_text,
            decision_summary=(envelope or {}).get("decision_summary")
            or _rule_decision_summary(run),
            hypotheses_json=(envelope or {}).get("hypotheses") or [],
            completion_criteria_json=_plan_completion_criteria(run, envelope),
        )
        db.session.add(plan)
        db.session.flush()

        nodes = (
            _envelope_nodes(plan.id, envelope, run)
            if envelope
            else _rule_nodes(plan.id, run)
        )
        db.session.add_all(nodes)
        db.session.flush()
        edges = (
            _envelope_edges(plan.id, envelope)
            if envelope
            else _rule_edges(plan.id, run)
        )
        db.session.add_all(edges)

        run.plan_version = plan.plan_version
        run.planner_source = planner_source
        payload = {
            "plan_id": plan.id,
            "plan_version": plan.plan_version,
            "planner_source": planner_source,
            "nodes": [node.node_key for node in nodes],
        }
        if fallback_reason:
            payload["fallback_reason"] = fallback_reason
        self._writer.emit(
            run,
            event_type=EVENT_PLAN_CREATED,
            item_id=f"plan_v{plan.plan_version}",
            payload=payload,
            trace_id=trace_id,
        )
        self._agent_log.plan_created(
            run,
            planner_source=planner_source,
            plan_version=plan.plan_version,
            node_count=len(nodes),
            fallback_reason=fallback_reason,
            decision_summary=plan.decision_summary,
            trace_id=trace_id,
        )
        db.session.commit()
        return plan

    # ------------------------------------------------------------------ helpers

    def _raise_warning(self, run: AgentRun, code: str, trace_id: str) -> None:
        self._events.emit(
            run,
            EVENT_WARNING_RAISED,
            {"warning_codes": [code]},
            trace_id=trace_id,
        )

    def _emit_budget(self, run: AgentRun, status: dict, trace_id: str) -> None:
        payload = {
            "soft": status["soft"],
            "exhausted": status["exhausted"],
            "reached_codes": status["reached_codes"],
            "ratios": status["ratios"],
        }
        self._events.emit(run, EVENT_BUDGET_UPDATED, payload, trace_id=trace_id)
        if status["reached_codes"]:
            self._events.emit(
                run,
                EVENT_WARNING_RAISED,
                {"warning_codes": status["reached_codes"]},
                trace_id=trace_id,
            )


# ------------------------------------------------------------------ plan builders


_DEEP_AUDIT_REVIEW_FOCUS = (
    "围绕已完成基线扫描中的高危发现，核查代码位置、调用路径、"
    "输入传播、可利用性与证据缺口。"
)


def _run_mode(run: AgentRun) -> str:
    mode = run.mode
    return mode.value if hasattr(mode, "value") else str(mode)


def _is_deep_audit(run: AgentRun) -> bool:
    return _run_mode(run) == "deep_audit"


def _rule_decision_summary(run: AgentRun) -> str:
    if _is_deep_audit(run):
        return (
            "本地策略深度审计：清点快照 → 确定性基线扫描 → 覆盖分析与风险排序 "
            "→ 深度证据审查 → 运行摘要。"
        )
    return (
        "本地策略基线：清点快照 → 确定性基线扫描 → 覆盖分析 → 风险排序 "
        "→ 运行摘要。"
    )


def _plan_completion_criteria(run: AgentRun, envelope: dict | None) -> list[str]:
    criteria = list((envelope or {}).get("completion_criteria") or [])
    if not criteria:
        criteria = [
            "inventory 完成",
            "baseline_scan 完成",
            "coverage_analysis 完成",
            "risk_ranking 完成",
            "report 完成",
        ]
    if _is_deep_audit(run) and not any(
        "deep_review" in criterion for criterion in criteria
    ):
        criteria.append("deep_review 完成并产出可核验证据")
    return criteria


def _rule_nodes(plan_id: int, run: AgentRun) -> list[AgentPlanNode]:
    nodes = [
        AgentPlanNode(
            plan_id=plan_id,
            node_key="inventory",
            node_type=AgentPlanNodeType.INVENTORY.value,
            status=AgentPlanNodeStatus.READY.value,
            title="清点快照文件",
            description="读取快照文件元数据：文件数、字节数、扩展名与语言分布。",
            tool_name="inventory_snapshot",
        ),
        AgentPlanNode(
            plan_id=plan_id,
            node_key="baseline_scan",
            node_type=AgentPlanNodeType.BASELINE_SCAN.value,
            status=AgentPlanNodeStatus.PENDING.value,
            title="执行基线扫描",
            description="复用确定性扫描管线执行 SAST、SCA 与通用 Secret 扫描，持久化发现项。",
            tool_name="run_baseline_scan",
            depends_on_json=["inventory"],
        ),
        AgentPlanNode(
            plan_id=plan_id,
            node_key="coverage_analysis",
            node_type=AgentPlanNodeType.COVERAGE_ANALYSIS.value,
            status=AgentPlanNodeStatus.PENDING.value,
            title="分析扫描覆盖",
            description="生成文件级覆盖报告：基线覆盖、专用 SAST、通用扫描、排除与发现分布。",
            tool_name="get_scan_coverage",
            depends_on_json=["baseline_scan"],
        ),
        AgentPlanNode(
            plan_id=plan_id,
            node_key="risk_ranking",
            node_type=AgentPlanNodeType.RISK_RANKING.value,
            status=AgentPlanNodeStatus.PENDING.value,
            title="风险排序",
            description="复用可解释风险评分对发现项排序，输出严重/高危统计与 Top 列表。",
            tool_name="rank_findings",
            depends_on_json=["baseline_scan"],
        ),
    ]
    report_dependencies = ["coverage_analysis", "risk_ranking"]
    if _is_deep_audit(run):
        nodes.append(
            AgentPlanNode(
                plan_id=plan_id,
                node_key="deep_review",
                node_type=AgentPlanNodeType.SEMANTIC_REVIEW.value,
                status=AgentPlanNodeStatus.PENDING.value,
                title="执行深度证据审查",
                description=(
                    "围绕高危扫描发现核查代码位置、调用路径、输入传播、"
                    "可利用性与证据缺口。"
                ),
                tool_name="run_deep_review",
                input_json={"focus": _DEEP_AUDIT_REVIEW_FOCUS},
                depends_on_json=["coverage_analysis", "risk_ranking"],
            )
        )
        report_dependencies.append("deep_review")
    nodes.append(
        AgentPlanNode(
            plan_id=plan_id,
            node_key="report",
            node_type=AgentPlanNodeType.REPORT_GENERATION.value,
            status=AgentPlanNodeStatus.PENDING.value,
            title="生成运行摘要",
            description="汇总已完成的确定性证据，生成运行摘要 Artifact。",
            tool_name="finalize_agent_report",
            depends_on_json=report_dependencies,
        )
    )
    return nodes


def _rule_edges(plan_id: int, run: AgentRun) -> list[AgentPlanEdge]:
    edges = [
        AgentPlanEdge(
            plan_id=plan_id,
            from_node="inventory",
            to_node="baseline_scan",
            edge_type=AgentPlanEdgeType.SUCCESS.value,
        ),
        AgentPlanEdge(
            plan_id=plan_id,
            from_node="baseline_scan",
            to_node="coverage_analysis",
            edge_type=AgentPlanEdgeType.SUCCESS.value,
        ),
        AgentPlanEdge(
            plan_id=plan_id,
            from_node="baseline_scan",
            to_node="risk_ranking",
            edge_type=AgentPlanEdgeType.SUCCESS.value,
        ),
        AgentPlanEdge(
            plan_id=plan_id,
            from_node="coverage_analysis",
            to_node="report",
            edge_type=AgentPlanEdgeType.SUCCESS.value,
        ),
        AgentPlanEdge(
            plan_id=plan_id,
            from_node="risk_ranking",
            to_node="report",
            edge_type=AgentPlanEdgeType.SUCCESS.value,
        ),
    ]
    if _is_deep_audit(run):
        edges.extend(
            [
                AgentPlanEdge(
                    plan_id=plan_id,
                    from_node="coverage_analysis",
                    to_node="deep_review",
                    edge_type=AgentPlanEdgeType.SUCCESS.value,
                ),
                AgentPlanEdge(
                    plan_id=plan_id,
                    from_node="risk_ranking",
                    to_node="deep_review",
                    edge_type=AgentPlanEdgeType.SUCCESS.value,
                ),
                AgentPlanEdge(
                    plan_id=plan_id,
                    from_node="deep_review",
                    to_node="report",
                    edge_type=AgentPlanEdgeType.SUCCESS.value,
                ),
            ]
        )
    return edges


def _envelope_nodes(
    plan_id: int,
    envelope: dict,
    run: AgentRun,
) -> list[AgentPlanNode]:
    """Map validated envelope nodes to durable rows; first node is READY."""
    nodes = []
    for index, item in enumerate(envelope["nodes"]):
        nodes.append(
            AgentPlanNode(
                plan_id=plan_id,
                node_key=item["key"],
                node_type=item["type"],
                status=(
                    AgentPlanNodeStatus.READY.value
                    if index == 0
                    else AgentPlanNodeStatus.PENDING.value
                ),
                title=item["title"],
                description=item["description"],
                tool_name=item["tool_name"],
                input_json=_envelope_node_input(run, item),
                depends_on_json=(
                    [
                        edge["from"]
                        for edge in envelope["edges"]
                        if edge["to"] == item["key"]
                    ]
                    or None
                ),
            )
        )
    return nodes


def _envelope_node_input(run: AgentRun, item: dict) -> dict | None:
    if (
        _is_deep_audit(run)
        and item["key"] == "deep_review"
        and item["type"] == AgentPlanNodeType.SEMANTIC_REVIEW.value
    ):
        return {"focus": _DEEP_AUDIT_REVIEW_FOCUS}
    return None


def _envelope_edges(plan_id: int, envelope: dict) -> list[AgentPlanEdge]:
    return [
        AgentPlanEdge(
            plan_id=plan_id,
            from_node=edge["from"],
            to_node=edge["to"],
            edge_type=AgentPlanEdgeType.SUCCESS.value,
        )
        for edge in envelope["edges"]
    ]


def _snapshot_summary(run: AgentRun) -> dict | None:
    from app.models.security import ProjectSnapshot, ScanTask, SecurityFinding

    snapshot = db.session.get(ProjectSnapshot, run.snapshot_id)
    if snapshot is None:
        return None
    summary: dict = {
        "file_count": snapshot.file_count,
        "total_bytes": snapshot.total_bytes,
        "source_type": snapshot.source_type,
    }
    task = (
        ScanTask.query.filter_by(snapshot_id=snapshot.id)
        .order_by(ScanTask.id.desc())
        .first()
    )
    if task is not None:
        summary["latest_scan_task_id"] = task.id
        summary["findings_count"] = SecurityFinding.query.filter_by(task_id=task.id).count()
    return summary


def _budget_payload(run: AgentRun) -> dict:
    return {
        "max_llm_calls": run.max_llm_calls,
        "max_tool_calls": run.max_tool_calls,
        "max_total_tokens": run.max_total_tokens,
        "max_estimated_cost": float(run.max_estimated_cost) if run.max_estimated_cost is not None else None,
        "max_wall_clock_seconds": run.max_wall_clock_seconds,
    }
