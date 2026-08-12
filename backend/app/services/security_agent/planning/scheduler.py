# -*- coding: utf-8 -*-
"""PlanScheduler（T06，spec §9.2/§9.3）：运行时按依赖计算 READY/BLOCKED。

- 只允许执行 READY 节点；SUCCESS 边要求上游 SUCCEEDED（策略允许时 SKIPPED 可满足）；
- FAILED / BLOCKED / CANCELED 上游使下游进入 BLOCKED，绝不进入 Executor；
- 纯计算模块：不调用模型、不调用工具、不落库，由 runner 应用状态。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanEdgeType,
    AgentPlanNode,
    AgentPlanNodeStatus,
)

_SATISFYING_STATUSES = {
    AgentPlanNodeStatus.SUCCEEDED.value,
}
_BLOCKING_STATUSES = {
    AgentPlanNodeStatus.FAILED.value,
    AgentPlanNodeStatus.BLOCKED.value,
    AgentPlanNodeStatus.CANCELED.value,
}
_WAITING_STATUSES = {
    AgentPlanNodeStatus.PENDING.value,
    AgentPlanNodeStatus.READY.value,
}


@dataclass(frozen=True)
class ScheduleState:
    ready: tuple[AgentPlanNode, ...] = ()
    blocked: tuple[str, ...] = ()
    unsatisfied: tuple[str, ...] = ()


class PlanScheduler:
    """按依赖解析一个计划版本的可执行状态（纯函数，无副作用）。"""

    def __init__(self, allow_skipped_to_satisfy: bool = True) -> None:
        self._allow_skipped = allow_skipped_to_satisfy

    def dependencies(self, plan: AgentPlan) -> dict[str, set[str]]:
        """edges → {to_node_key: {from_node_key, ...}}；无 edge 视为无依赖。"""
        deps: dict[str, set[str]] = {
            node.node_key: set() for node in plan.nodes
        }
        for edge in plan.edges:
            if edge.edge_type != AgentPlanEdgeType.SUCCESS.value:
                continue
            deps.setdefault(edge.to_node, set()).add(edge.from_node)
        return deps

    def _status_of(self, plan: AgentPlan, node_key: str) -> str:
        for node in plan.nodes:
            if node.node_key == node_key:
                return _status_value(node.status)
        return AgentPlanNodeStatus.PENDING.value

    def _satisfies(self, plan: AgentPlan, node_key: str) -> bool:
        status = self._status_of(plan, node_key)
        if status == AgentPlanNodeStatus.SUCCEEDED.value:
            return True
        if (
            self._allow_skipped
            and status == AgentPlanNodeStatus.SKIPPED.value
        ):
            return True
        return False

    def _blocks(self, plan: AgentPlan, node_key: str) -> bool:
        return self._status_of(plan, node_key) in _BLOCKING_STATUSES

    def compute(self, plan: AgentPlan) -> ScheduleState:
        """计算 READY / BLOCKED / 未满足依赖的节点集合。"""
        deps = self.dependencies(plan)
        ready: list[AgentPlanNode] = []
        blocked: list[str] = []
        unsatisfied: list[str] = []
        for node in plan.nodes:
            status = _status_value(node.status)
            if status not in _WAITING_STATUSES:
                continue
            node_deps = deps.get(node.node_key, set())
            blocking = [key for key in node_deps if self._blocks(plan, key)]
            if blocking:
                blocked.append(node.node_key)
                continue
            missing = [
                key for key in sorted(node_deps)
                if not self._satisfies(plan, key)
            ]
            if missing:
                unsatisfied.append(node.node_key)
                continue
            ready.append(node)
        ready.sort(key=lambda item: item.id)
        return ScheduleState(
            ready=tuple(ready),
            blocked=tuple(sorted(blocked)),
            unsatisfied=tuple(sorted(unsatisfied)),
        )

    def ready_nodes(self, plan: AgentPlan) -> list[AgentPlanNode]:
        return list(self.compute(plan).ready)

    def blocked_nodes(self, plan: AgentPlan) -> list[str]:
        return list(self.compute(plan).blocked)


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)
