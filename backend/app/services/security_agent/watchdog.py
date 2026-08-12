# -*- coding: utf-8 -*-
"""A10 韧性服务：Watchdog 与开放 Run 恢复。

- watch_open_runs：扫描租约过期/卡死的 run——超过 AGENT_WATCHDOG_STALE_SECONDS
  仍停留在执行态且无有效租约的，标记失败（保留已产生的证据与事件）；
  awaiting_approval 且审批全部已处理（approved/rejected）的，恢复执行。
- recover_open_runs：进程重启后把开放状态 run 重新入队执行（幂等）。
两个命令均通过 flask CLI 触发：`flask --app run agent-watchdog` /
`flask --app run recover-open-runs`。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app import db
from app.models.agent_approval import AgentApproval, ApprovalStatus
from app.models.agent_runtime import AgentRun, AgentRunStatus
from app.services.security_agent.state_machine import AgentStateMachine

logger = logging.getLogger(__name__)

DEFAULT_STALE_SECONDS = 1800
DEFAULT_MAX_RECOVERIES = 20

_ACTIVE_STATUSES = {
    AgentRunStatus.QUEUED.value,
    AgentRunStatus.PREPARING.value,
    AgentRunStatus.MAPPING_REPOSITORY.value,
    AgentRunStatus.PLANNING.value,
    AgentRunStatus.VALIDATING_PLAN.value,
    AgentRunStatus.EXECUTING_TOOLS.value,
    AgentRunStatus.EVALUATING_EVIDENCE.value,
    AgentRunStatus.REPLANNING.value,
    AgentRunStatus.DEEP_REVIEWING.value,
    AgentRunStatus.AWAITING_APPROVAL.value,
    AgentRunStatus.GENERATING_REPORT.value,
}

_RECOVERABLE_STATUSES = {
    AgentRunStatus.QUEUED.value,
    AgentRunStatus.PREPARING.value,
    AgentRunStatus.EXECUTING_TOOLS.value,
    AgentRunStatus.EVALUATING_EVIDENCE.value,
    AgentRunStatus.AWAITING_APPROVAL.value,
}


def watch_open_runs(*, stale_seconds: int = DEFAULT_STALE_SECONDS) -> dict:
    """扫描卡死 run：租约过期 → 失败；审批已处理 → 恢复执行。"""
    state = AgentStateMachine()
    stale_cutoff = datetime.utcnow() - timedelta(seconds=max(60, stale_seconds))
    failed: list[int] = []
    recovered: list[int] = []
    resumed: list[int] = []

    runs = AgentRun.query.filter(AgentRun.status.in_(list(_ACTIVE_STATUSES))).all()
    for run in runs:
        status = run.status.value if hasattr(run.status, "value") else str(run.status)
        if status == AgentRunStatus.AWAITING_APPROVAL.value:
            pending = (
                AgentApproval.query.filter_by(
                    run_id=run.id, status=ApprovalStatus.PENDING.value
                ).first()
                is not None
            )
            if pending:
                continue
            resumed.append(run.id)
            _resume_or_fail(run, state)
            continue

        lease_ok = run.lease_expires_at is not None and run.lease_expires_at > datetime.utcnow()
        heartbeat_ok = run.heartbeat_at is not None and run.heartbeat_at > stale_cutoff
        if lease_ok or heartbeat_ok:
            continue
        try:
            state.transition(
                run,
                AgentRunStatus.FAILED,
                actor_id=run.created_by,
                reason="Watchdog：执行租约过期，判定为卡死任务",
            )
        except Exception:
            continue
        run.error_code = "AGENT_WATCHDOG_STALE"
        failed.append(run.id)
    db.session.commit()
    logger.info("Watchdog done: failed=%s resumed=%s", failed, resumed)
    return {"failed": failed, "resumed": resumed}


def recover_open_runs(*, max_recoveries: int = DEFAULT_MAX_RECOVERIES) -> dict:
    """T09：进程重启后按 lease/checkpoint/recovery policy 恢复开放 run。

    - 只恢复 lease 已过期或从未获取 lease 的 run（另一 Worker 持有 lease 时跳过）；
    - 超过恢复上限显式停止并保留证据（不盲目全量重跑）；
    - 幂等：终态 run 跳过。
    """
    from app.services.security_agent.loop.lease_service import LeaseService
    from app.services.security_agent.service import AgentRunService

    leases = LeaseService()
    runs = AgentRun.query.filter(AgentRun.status.in_(list(_RECOVERABLE_STATUSES))).all()
    recovered: list[int] = []
    skipped_leased: list[int] = []
    for run in runs:
        if len(recovered) >= max_recoveries:
            logger.warning(
                "Recovery limit reached (%s), stopping before run=%s",
                max_recoveries,
                run.id,
            )
            break
        status = run.status.value if hasattr(run.status, "value") else str(run.status)
        if status == AgentRunStatus.AWAITING_APPROVAL.value:
            pending = (
                AgentApproval.query.filter_by(
                    run_id=run.id, status=ApprovalStatus.PENDING.value
                ).first()
                is not None
            )
            if pending:
                continue
        owner, expires_at = leases.current(run.id)
        if owner is not None and expires_at is not None and expires_at > datetime.utcnow():
            skipped_leased.append(run.id)
            continue
        run.lease_owner = None
        run.lease_expires_at = None
        db.session.flush()
        AgentRunService().execute_open_run(run.id, "recover-open-runs")
        recovered.append(run.id)
    db.session.commit()
    logger.info(
        "Recover open runs: %s (skipped leased: %s)",
        recovered,
        skipped_leased,
    )
    return {"recovered": recovered, "skipped_leased": skipped_leased}


def _resume_or_fail(run: AgentRun, state: AgentStateMachine) -> None:
    """awaiting_approval 且审批已处理：转 executing_tools（failover 兜底失败则标记失败）。"""
    try:
        state.transition(
            run,
            AgentRunStatus.EXECUTING_TOOLS,
            actor_id=run.created_by,
            reason="Watchdog：审批已处理，恢复执行",
        )
    except Exception:
        try:
            state.transition(
                run,
                AgentRunStatus.FAILED,
                actor_id=run.created_by,
                reason="Watchdog：审批已处理但无法恢复执行",
            )
            run.error_code = "AGENT_WATCHDOG_RESUME_FAILED"
        except Exception:
            pass


def register_watchdog_commands(app) -> None:
    """注册 flask CLI 命令（幂等）。"""

    @app.cli.command("agent-watchdog")
    def agent_watchdog_cli():
        """扫描卡死 Agent run：租约过期失败化，审批已处理恢复执行。"""
        result = watch_open_runs()
        print(f"Watchdog: failed={result['failed']} resumed={result['resumed']}")

    @app.cli.command("recover-open-runs")
    def recover_open_runs_cli():
        """把开放状态的 Agent run 重新入队执行（进程重启后使用）。"""
        result = recover_open_runs()
        print(f"Recovered open runs: {result['recovered']}")
