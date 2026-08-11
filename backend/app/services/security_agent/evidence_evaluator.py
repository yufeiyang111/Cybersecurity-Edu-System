# -*- coding: utf-8 -*-
"""证据评估：将 Run 的确定性执行结果压缩为结构化指标（A5）。

输入：最新计划节点状态、SecurityFinding 分布、覆盖报告摘要、warning_codes。
输出：EvidenceSummary —— 供 StrategyCatalog 判定是否需要重规划。
本模块只做只读评估，不落库、不改状态；决策与落库在 strategy_catalog /
replanner / decision_records 中完成。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app import db
from app.models.agent_runtime import (
    AgentPlan,
    AgentPlanNodeStatus,
    AgentRun,
    AgentRunStatus,
)
from app.models.security import ScanTask, SecurityFinding


@dataclass(frozen=True)
class EvidenceSummary:
    """一次证据评估的结构化结果（全字段只读）。"""

    total_findings: int = 0
    high_severity_count: int = 0
    high_finding_files: tuple[str, ...] = ()
    coverage_ratio: float | None = None
    failed_node_keys: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()
    plan_completed: bool = True
    graph_built: bool = False
    findings_per_file: int = 0
    scan_task_id: int | None = None


class EvidenceEvaluator:
    """从 DB 只读聚合一次 Run 的证据摘要。"""

    # ------------------------------------------------------------------ public

    def evaluate(self, run: AgentRun, plan: AgentPlan | None = None) -> EvidenceSummary:
        task = self._latest_task(run)
        findings_count, high_count, files_with_findings = self._finding_summary(task)
        coverage_ratio = self._coverage_ratio(run, task)
        failed = self._failed_node_keys(plan)
        warnings = tuple(run.warning_codes or [])
        plan_completed = self._plan_completed(plan)
        graph_built = self._graph_built(run)

        return EvidenceSummary(
            total_findings=findings_count,
            high_severity_count=high_count,
            high_finding_files=self._high_finding_files(task),
            coverage_ratio=coverage_ratio,
            failed_node_keys=failed,
            warning_codes=warnings,
            plan_completed=plan_completed,
            graph_built=graph_built,
            findings_per_file=files_with_findings,
            scan_task_id=task.id if task is not None else None,
        )

    # ------------------------------------------------------------------ helpers

    def _latest_task(self, run: AgentRun) -> ScanTask | None:
        if run.snapshot_id is None:
            return None
        return (
            ScanTask.query.filter_by(snapshot_id=run.snapshot_id)
            .order_by(ScanTask.id.desc())
            .first()
        )

    def _high_finding_files(self, task: ScanTask | None) -> tuple[str, ...]:
        if task is None:
            return ()
        rows = (
            db.session.query(SecurityFinding.file_path)
            .filter(
                SecurityFinding.task_id == task.id,
                SecurityFinding.severity.in_(["critical", "high"]),
            )
            .order_by(SecurityFinding.id.asc())
            .all()
        )
        seen: list[str] = []
        for (path,) in rows:
            if path and path not in seen:
                seen.append(path)
        return tuple(seen)

    def _finding_summary(self, task: ScanTask | None) -> tuple[int, int, int]:
        if task is None:
            return 0, 0, 0
        rows = (
            db.session.query(
                SecurityFinding.severity,
                SecurityFinding.file_path,
            )
            .filter(SecurityFinding.task_id == task.id)
            .all()
        )
        high = sum(1 for severity, _ in rows if severity in {"critical", "high"})
        files = len({path for _, path in rows if path})
        return len(rows), high, files

    def _coverage_ratio(self, run: AgentRun, task: ScanTask | None) -> float | None:
        if task is None:
            return None
        try:
            from app.services.scan_coverage.summary import build_coverage_summary

            summary = build_coverage_summary(task.id)
        except Exception:
            return None
        if summary is None:
            return None
        scanned = summary.get("baseline_scanned") or 0
        total = (summary.get("extracted_files") or 0) or (summary.get("archive_files") or 0)
        if total <= 0:
            return None
        return round(min(1.0, scanned / total), 4)

    def _failed_node_keys(self, plan: AgentPlan | None) -> tuple[str, ...]:
        if plan is None:
            return ()
        return tuple(
            node.node_key
            for node in plan.nodes
            if node.status == AgentPlanNodeStatus.FAILED.value
        )

    def _plan_completed(self, plan: AgentPlan | None) -> bool:
        """全部节点进入终态且无失败节点才算完成；failed 视为证据缺口。"""
        if plan is None:
            return True
        unfinished = {
            AgentPlanNodeStatus.PENDING.value,
            AgentPlanNodeStatus.READY.value,
            AgentPlanNodeStatus.RUNNING.value,
            AgentPlanNodeStatus.FAILED.value,
            AgentPlanNodeStatus.BLOCKED.value,
        }
        return not any(node.status in unfinished for node in plan.nodes)

    def _graph_built(self, run: AgentRun) -> bool:
        if run.snapshot_id is None:
            return False
        from app.services.project_security_graph import graph_queries
        from app.services.project_security_graph.contracts import DEFAULT_MAPPER_VERSION

        try:
            return graph_queries.graph_summary(run.snapshot_id, DEFAULT_MAPPER_VERSION) is not None
        except Exception:
            return False


def _is_terminal(run: AgentRun) -> bool:
    status = run.status.value if hasattr(run.status, "value") else str(run.status)
    return status in {
        AgentRunStatus.COMPLETED.value,
        AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
        AgentRunStatus.PARTIAL.value,
        AgentRunStatus.FAILED.value,
        AgentRunStatus.CANCELED.value,
    }
