# -*- coding: utf-8 -*-
"""审批服务（A7）：请求创建（digest 防重放）、单次决策、过期处理、恢复执行。

- request：幂等（operation_digest 唯一），发 approval.requested + warning。
- resolve：单次使用（pending→approved/rejected），过期拒绝，
  角色校验（approval_policy.can_resolve），决策写 Event + AuditEvent；
  approved 时应用 proposed 配置（如新预算）并触发 run 恢复执行。
- rejected/expired 不自动放行：rejected 时 run 转 partial（确定性结果保留）。
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.agent_approval import (
    AgentApproval,
    ApprovalOperationType,
    ApprovalStatus,
)
from app.models.agent_runtime import AgentRun, AgentRunStatus
from app.models.security import AuditEvent
from app.services.agent_observability import AgentLogger
from app.services.security_agent.approval_policy import (
    APPROVAL_EXPIRES_MINUTES,
    can_resolve,
    operation_label,
    risk_for_operation,
)
from app.services.security_agent.contracts import (
    EVENT_APPROVAL_REQUESTED,
    EVENT_APPROVAL_RESOLVED,
    EVENT_WARNING_RAISED,
)
from app.services.security_agent.event_service import EventService
from app.services.security_agent.state_machine import AgentStateError, AgentStateMachine


class ApprovalError(ValueError):
    pass


class ApprovalExpiredError(ApprovalError):
    pass


class ApprovalConflictError(ApprovalError):
    pass


def _digest(run_id: int, operation_type: str, scope: dict, proposed: dict) -> str:
    payload = f"{run_id}:{operation_type}:{sorted(scope.items())}:{sorted(proposed.items())}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ApprovalService:
    def __init__(self, events: EventService | None = None) -> None:
        self._events = events or EventService()
        self._state = AgentStateMachine()
        self._agent_log = AgentLogger()

    # ------------------------------------------------------------------ request

    def request(
        self,
        run: AgentRun,
        *,
        operation_type: str = ApprovalOperationType.BUDGET_INCREASE.value,
        reason: str,
        affected_scope: dict | None = None,
        proposed: dict | None = None,
        requester_id: int | None = None,
        expires_minutes: int = APPROVAL_EXPIRES_MINUTES,
        trace_id: str | None = None,
    ) -> AgentApproval:
        scope = affected_scope or {}
        proposed = proposed or {}
        digest = _digest(run.id, operation_type, scope, proposed)
        existing = AgentApproval.query.filter_by(operation_digest=digest).one_or_none()
        if existing is not None:
            return existing

        approval = AgentApproval(
            run_id=run.id,
            workspace_id=run.workspace_id,
            operation_type=operation_type,
            risk_level=risk_for_operation(operation_type),
            reason=reason[:1000],
            affected_scope_json=scope,
            operation_digest=digest,
            proposed_json=proposed,
            requested_by=requester_id,
            expires_at=datetime.utcnow() + timedelta(minutes=max(1, expires_minutes)),
        )
        db.session.add(approval)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            existing = AgentApproval.query.filter_by(operation_digest=digest).one_or_none()
            if existing is not None:
                return existing
            raise

        self._events.emit(
            run,
            EVENT_APPROVAL_REQUESTED,
            {
                "approval_id": approval.id,
                "operation_type": approval.operation_type,
                "operation_label": operation_label(approval.operation_type),
                "risk_level": approval.risk_level,
                "reason": approval.reason,
                "affected_scope": approval.affected_scope_json or {},
                "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
            },
            trace_id=trace_id,
        )
        self._events.emit(
            run,
            EVENT_WARNING_RAISED,
            {"warning_codes": ["AGENT_APPROVAL_REQUIRED"], "approval_id": approval.id},
            trace_id=trace_id,
        )
        self._agent_log.run_event(
            "run.approval_requested",
            run,
            trace_id=trace_id,
            approval_id=approval.id,
            operation_type=approval.operation_type,
            risk_level=approval.risk_level,
        )
        db.session.commit()
        return approval

    # ------------------------------------------------------------------ resolve

    def resolve(
        self,
        run: AgentRun,
        approval_id: int,
        *,
        decision: str,
        comment: str,
        resolver_id: int,
        resolver_role: str | None,
        trace_id: str | None = None,
    ) -> AgentApproval:
        if decision not in {ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value}:
            raise ApprovalError("decision 必须是 approved 或 rejected")
        approval = db.session.get(AgentApproval, approval_id)
        if approval is None or approval.run_id != run.id:
            raise ApprovalError("审批请求不存在")
        if approval.status != ApprovalStatus.PENDING.value:
            raise ApprovalConflictError(f"审批请求已处理（{approval.status}）")
        if not can_resolve(approval, resolver_role):
            raise ApprovalError("当前角色无权批准该风险级别的操作")

        now = datetime.utcnow()
        if approval.expires_at is not None and now > approval.expires_at:
            approval.status = ApprovalStatus.EXPIRED.value
            approval.resolved_at = now
            db.session.commit()
            self._events.emit(
                run,
                EVENT_APPROVAL_RESOLVED,
                {
                    "approval_id": approval.id,
                    "decision": ApprovalStatus.EXPIRED.value,
                    "reason": "审批请求已过期",
                },
                trace_id=trace_id,
            )
            self._events.emit(
                run,
                EVENT_WARNING_RAISED,
                {"warning_codes": ["AGENT_APPROVAL_EXPIRED"], "approval_id": approval.id},
                trace_id=trace_id,
            )
            raise ApprovalExpiredError("审批请求已过期，请重新发起")

        approval.status = decision
        approval.decision_comment = (comment or "")[:1000]
        approval.resolver_id = resolver_id
        approval.resolved_at = now
        db.session.add(
            AuditEvent(
                workspace_id=run.workspace_id,
                actor_id=resolver_id,
                action="agent_approval.resolve",
                target_type="agent_approval",
                target_id=approval.id,
                metadata_json={
                    "run_id": run.id,
                    "operation_type": approval.operation_type,
                    "risk_level": approval.risk_level,
                    "decision": decision,
                    "comment": (comment or "")[:300],
                },
            )
        )
        db.session.flush()

        self._events.emit(
            run,
            EVENT_APPROVAL_RESOLVED,
            {
                "approval_id": approval.id,
                "decision": decision,
                "comment": (comment or "")[:300],
                "operation_type": approval.operation_type,
            },
            trace_id=trace_id,
        )

        if decision == ApprovalStatus.APPROVED.value:
            self._apply_proposed(run, approval)
            self._resume_run(run, trace_id=trace_id)
        else:
            self._reject_run(run, approval, trace_id=trace_id)

        self._agent_log.run_event(
            "run.approval_resolved",
            run,
            trace_id=trace_id,
            approval_id=approval.id,
            decision=decision,
            operation_type=approval.operation_type,
        )
        db.session.commit()
        return approval

    # ------------------------------------------------------------------ read

    def list_for_run(self, run_id: int, *, limit: int = 50) -> list[AgentApproval]:
        return (
            AgentApproval.query.filter_by(run_id=run_id)
            .order_by(AgentApproval.id.desc())
            .limit(limit)
            .all()
        )

    def list_for_workspace(
        self,
        workspace_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[AgentApproval], int]:
        query = AgentApproval.query.filter_by(workspace_id=workspace_id)
        if status:
            query = query.filter(AgentApproval.status == status)
        total = query.count()
        page_size = min(max(1, page_size), 100)
        offset = max(0, page - 1) * page_size
        rows = (
            query.order_by(AgentApproval.id.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return rows, total

    def has_pending(self, run_id: int) -> bool:
        return (
            AgentApproval.query.filter_by(
                run_id=run_id, status=ApprovalStatus.PENDING.value
            ).first()
            is not None
        )

    # ------------------------------------------------------------------ helpers

    def _apply_proposed(self, run: AgentRun, approval: AgentApproval) -> None:
        proposed = approval.proposed_json or {}
        budget = proposed.get("budget") or {}
        changed = False
        if isinstance(budget, dict):
            for key, value in budget.items():
                if key in {
                    "max_llm_calls",
                    "max_tool_calls",
                    "max_total_tokens",
                    "max_wall_clock_seconds",
                    "max_deep_review_files",
                } and isinstance(value, int) and value > 0:
                    setattr(run, key, value)
                    changed = True
                elif key == "max_estimated_cost" and isinstance(value, (int, float)) and value > 0:
                    run.max_estimated_cost = float(value)
                    changed = True
        run.warning_codes = [code for code in (run.warning_codes or []) if code != "AGENT_BUDGET_EXHAUSTED"]
        if changed:
            run.updated_at = datetime.utcnow()

    def _resume_run(self, run: AgentRun, *, trace_id: str | None) -> None:
        try:
            self._state.transition(
                run,
                AgentRunStatus.EXECUTING_TOOLS,
                actor_id=run.created_by,
                reason="审批通过，继续执行",
                trace_id=trace_id,
            )
        except AgentStateError:
            return
        db.session.flush()
        from app.services.security_agent.service import AgentRunService

        AgentRunService().execute_open_run(run.id, trace_id or "approval-resume")

    def _reject_run(self, run: AgentRun, approval: AgentApproval, *, trace_id: str | None) -> None:
        try:
            self._state.transition(
                run,
                AgentRunStatus.PARTIAL,
                actor_id=run.created_by,
                reason=f"审批被拒绝（{approval.operation_type}），保留已完成的确定性结果",
                trace_id=trace_id,
            )
        except AgentStateError:
            return
        self._events.emit(
            run,
            EVENT_WARNING_RAISED,
            {"warning_codes": ["AGENT_APPROVAL_REJECTED"], "approval_id": approval.id},
            trace_id=trace_id,
        )


def get_approval_service(events: EventService | None = None) -> ApprovalService:
    return ApprovalService(events)
