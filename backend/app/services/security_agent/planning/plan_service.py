# -*- coding: utf-8 -*-
"""PlanService（T06，spec §9.4）：版本化计划服务与 Plan Patch 治理。

- create_version：复制旧版本并追加合法节点，写 Decision Record 与 v2 事件；
- apply_patch：只允许追加/替换合法未完成节点，禁止改写已完成历史、
  禁止删除或伪造强制基线；相同 patch 幂等（目标版本已存在则复用）；
- 版本上限：AGENT_MAX_PLAN_VERSIONS（默认 5，含初始计划）。
"""
from __future__ import annotations

import logging
from dataclasses import asdict

from flask import current_app

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanEdge,
    AgentPlanEdgeType,
    AgentPlanNode,
    AgentPlanNodeStatus,
    AgentRun,
)
from app.services.security_agent.contracts import (
    EVENT_WARNING_RAISED,
)
from app.services.security_agent.decision_records import DecisionRecords
from app.services.security_agent.event_service import EventService
from app.services.security_agent.planning.completion_criteria import (
    MANDATORY_BASELINE_KEYS,
)
from app.services.security_agent.strategy_catalog import NodeSpec
from app.services.security_agent.timeline.contracts import (
    EVENT_PLAN_UPDATED,
)
from app.services.security_agent.timeline.event_writer import EventWriter

logger = logging.getLogger(__name__)

DEFAULT_MAX_PLAN_VERSIONS = 5

_TERMINAL_NODE_STATUSES = frozenset(
    {
        AgentPlanNodeStatus.SUCCEEDED.value,
        AgentPlanNodeStatus.FAILED.value,
        AgentPlanNodeStatus.CANCELED.value,
        AgentPlanNodeStatus.SUPERSEDED.value,
    }
)


class PlanServiceError(ValueError):
    """Plan Patch 非法：改写历史、删除基线或超版本上限。"""


class PlanService:
    def __init__(
        self,
        events: EventService | None = None,
        decisions: DecisionRecords | None = None,
    ) -> None:
        self._events = events or EventService()
        self._decisions = decisions or DecisionRecords(self._events)
        self._writer = EventWriter()

    # ---------------------------------------------------------------- versions

    def create_version(
        self,
        run: AgentRun,
        supersedes: AgentPlan,
        *,
        node_specs: tuple[NodeSpec, ...],
        reason_code: str,
        decision_type: str,
        decision_summary: str = "",
        trace_id: str | None = None,
    ) -> AgentPlan | None:
        """创建新计划版本；超上限返回 None 并发出警告（不静默）。"""
        max_versions = _config_int("AGENT_MAX_PLAN_VERSIONS", DEFAULT_MAX_PLAN_VERSIONS)
        if supersedes.plan_version + 1 > max_versions:
            self._raise_limit(run, "AGENT_PLAN_VERSION_LIMIT", trace_id)
            return None

        existing = (
            AgentPlan.query.filter_by(
                run_id=run.id, plan_version=supersedes.plan_version + 1
            ).first()
        )
        if existing is not None:
            return existing

        plan = self._build_version(run, supersedes, node_specs)
        self._persist(run, plan, supersedes, node_specs, reason_code,
                      decision_type, decision_summary, trace_id)
        return plan

    def apply_patch(
        self,
        run: AgentRun,
        plan: AgentPlan,
        *,
        patch: dict,
        reason_code: str,
        decision_type: str,
        decision_summary: str = "",
        trace_id: str | None = None,
    ) -> AgentPlan:
        """应用 Plan Patch（Controller 校验后版本化）。"""
        self._validate_patch(plan, patch)
        add_specs: list[NodeSpec] = []
        for raw in patch.get("add_nodes") or []:
            add_specs.append(_coerce_spec(raw))
        for raw in patch.get("replace_nodes") or []:
            add_specs.append(_coerce_spec(raw))
        return self.create_version(
            run,
            plan,
            node_specs=tuple(add_specs),
            reason_code=reason_code,
            decision_type=decision_type,
            decision_summary=decision_summary,
            trace_id=trace_id,
        )

    # ---------------------------------------------------------------- patch validation

    def _validate_patch(self, plan: AgentPlan, patch: dict) -> None:
        if not isinstance(patch, dict):
            raise PlanServiceError("patch 必须是对象")
        remove_keys = patch.get("remove_nodes") or []
        replace_keys = {
            _coerce_spec(raw).key for raw in (patch.get("replace_nodes") or [])
        }
        add_keys = {
            _coerce_spec(raw).key for raw in (patch.get("add_nodes") or [])
        }
        existing_keys = {node.node_key for node in plan.nodes}
        statuses = {node.node_key: _status_value(node.status) for node in plan.nodes}

        for key in remove_keys:
            if key in MANDATORY_BASELINE_KEYS:
                raise PlanServiceError(
                    f"强制基线节点 {key} 不可删除"
                )
            if statuses.get(key) in _TERMINAL_NODE_STATUSES:
                raise PlanServiceError(
                    f"已完成节点 {key} 不可删除"
                )
        for key in replace_keys | add_keys:
            if not isinstance(key, str) or not key:
                raise PlanServiceError("节点 key 必须是非空字符串")
            if key in add_keys and key in existing_keys:
                raise PlanServiceError(f"节点 key 已存在：{key}")
        for key in replace_keys:
            if key not in existing_keys:
                raise PlanServiceError(f"替换目标节点不存在：{key}")
            if key in MANDATORY_BASELINE_KEYS:
                raise PlanServiceError(f"强制基线节点 {key} 不可替换")
            if statuses.get(key) in _TERMINAL_NODE_STATUSES:
                raise PlanServiceError(f"已完成节点 {key} 不可改写")

    # ---------------------------------------------------------------- build

    def _build_version(
        self,
        run: AgentRun,
        supersedes: AgentPlan,
        node_specs: tuple[NodeSpec, ...],
    ) -> AgentPlan:
        plan = AgentPlan(
            run_id=run.id,
            plan_version=supersedes.plan_version + 1,
            planner_source=run.planner_source or "rule_based_policy",
            objective=supersedes.objective,
            decision_summary=supersedes.decision_summary,
            hypotheses_json=supersedes.hypotheses_json or [],
            completion_criteria_json=supersedes.completion_criteria_json or [],
        )
        db.session.add(plan)
        db.session.flush()

        existing_keys: set[str] = set()
        for node in supersedes.nodes:
            existing_keys.add(node.node_key)
            db.session.add(
                AgentPlanNode(
                    plan_id=plan.id,
                    node_key=node.node_key,
                    node_type=node.node_type,
                    status=node.status,
                    title=node.title,
                    description=node.description,
                    tool_name=node.tool_name,
                    input_json=node.input_json,
                    depends_on_json=node.depends_on_json,
                    input_artifact_refs=node.input_artifact_refs,
                    output_artifact_refs=node.output_artifact_refs,
                    retry_count=node.retry_count,
                )
            )
        for edge in supersedes.edges:
            db.session.add(
                AgentPlanEdge(
                    plan_id=plan.id,
                    from_node=edge.from_node,
                    to_node=edge.to_node,
                    edge_type=edge.edge_type,
                    condition_json=edge.condition_json,
                )
            )
        db.session.flush()

        added: list[AgentPlanNode] = []
        for spec in node_specs:
            if spec.key in existing_keys:
                continue
            depends = [key for key in spec.depends_on if key in existing_keys] or None
            node = AgentPlanNode(
                plan_id=plan.id,
                node_key=spec.key,
                node_type=spec.node_type,
                status=AgentPlanNodeStatus.PENDING.value,
                title=spec.title,
                description=spec.description,
                tool_name=spec.tool_name,
                input_json=spec.input or None,
                depends_on_json=depends,
            )
            db.session.add(node)
            added.append(node)
            existing_keys.add(spec.key)
            if depends:
                db.session.add(
                    AgentPlanEdge(
                        plan_id=plan.id,
                        from_node=depends[0],
                        to_node=spec.key,
                        edge_type=AgentPlanEdgeType.SUCCESS.value,
                    )
                )
        db.session.flush()
        if added:
            added[0].status = AgentPlanNodeStatus.READY.value
        return plan

    def _persist(
        self,
        run: AgentRun,
        plan: AgentPlan,
        supersedes: AgentPlan,
        node_specs: tuple[NodeSpec, ...],
        reason_code: str,
        decision_type: str,
        decision_summary: str,
        trace_id: str | None,
    ) -> None:
        run.plan_version = plan.plan_version
        run.replan_count = (run.replan_count or 0) + 1
        added_keys = [spec.key for spec in node_specs]
        self._decisions.record(
            run,
            plan_version=plan.plan_version,
            supersedes_version=supersedes.plan_version,
            reason_code=reason_code,
            decision_type=decision_type,
            detail={
                "decision_summary": decision_summary,
                "new_nodes": added_keys,
            },
            trace_id=trace_id,
        )
        self._writer.emit(
            run,
            event_type=EVENT_PLAN_UPDATED,
            item_id=f"plan_v{plan.plan_version}",
            payload={
                "plan_id": plan.id,
                "plan_version": plan.plan_version,
                "supersedes_version": supersedes.plan_version,
                "reason_code": reason_code,
                "decision_type": decision_type,
                "new_nodes": added_keys,
                "decision_summary": decision_summary,
            },
            trace_id=trace_id,
        )
        db.session.commit()

    # ---------------------------------------------------------------- helpers

    def _raise_limit(self, run: AgentRun, code: str, trace_id: str | None) -> None:
        logger.warning(
            "Plan version limit reached (run_id=%s)", run.id
        )
        self._events.emit(
            run,
            EVENT_WARNING_RAISED,
            {"warning_codes": [code]},
            trace_id=trace_id,
        )


def _coerce_spec(raw) -> NodeSpec:
    if isinstance(raw, NodeSpec):
        return raw
    if not isinstance(raw, dict):
        raise PlanServiceError("节点规格必须是 NodeSpec 或对象")
    try:
        return NodeSpec(
            key=str(raw["key"]),
            node_type=str(raw["node_type"]),
            title=str(raw.get("title") or raw["key"]),
            description=str(raw.get("description") or ""),
            tool_name=str(raw["tool_name"]),
            depends_on=tuple(raw.get("depends_on") or ()),
            input=raw.get("input") or {},
        )
    except KeyError as exc:
        raise PlanServiceError(f"节点规格缺少字段：{exc.args[0]}") from exc


def _config_int(key: str, default: int) -> int:
    if current_app is None:
        return default
    try:
        return int(current_app.config.get(key, default))
    except (TypeError, ValueError):
        return default


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)
