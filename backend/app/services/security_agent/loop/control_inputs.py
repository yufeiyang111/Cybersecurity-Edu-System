# -*- coding: utf-8 -*-
"""ControlInputService（T07，spec §8.4）：有序控制输入的幂等写入口。

HTTP 线程只负责幂等入队（Message + Control Input + v2 Event），绝不直接
创建 Plan 或执行工具；Agent Loop 在安全边界按确定性优先级应用：
cancel > pause > resume > approval_result > user_message > system_retry。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.agent_control import AgentControlInput
from app.models.agent_runtime import AgentRun
from app.services.security_agent.timeline.contracts import (
    EVENT_APPROVAL_RESOLVED,
    EVENT_RUN_STATE_CHANGED,
    EVENT_USER_MESSAGE_CREATED,
)
from app.services.security_agent.timeline.event_writer import EventWriter

ALLOWED_INPUT_TYPES = frozenset(
    {"user_message", "approval_result", "pause", "resume", "cancel", "system_retry"}
)

# 数字越小越先应用：取消优先于审批结果与用户消息
_INPUT_TYPE_PRIORITY = {
    "cancel": 0,
    "pause": 1,
    "resume": 2,
    "approval_result": 3,
    "user_message": 4,
    "system_retry": 5,
}

_TERMINAL_STATUSES = frozenset({"applied", "rejected", "superseded"})

_EVENT_BY_INPUT_TYPE = {
    "user_message": EVENT_USER_MESSAGE_CREATED,
    "approval_result": EVENT_APPROVAL_RESOLVED,
    "pause": EVENT_RUN_STATE_CHANGED,
    "resume": EVENT_RUN_STATE_CHANGED,
    "cancel": EVENT_RUN_STATE_CHANGED,
    "system_retry": EVENT_RUN_STATE_CHANGED,
}


class ControlInputError(ValueError):
    """控制输入非法：未知类型或重复应用。"""


class ControlInputService:
    def __init__(self, writer: EventWriter | None = None) -> None:
        self._writer = writer or EventWriter()

    # ---------------------------------------------------------------- enqueue

    def enqueue(
        self,
        run: AgentRun,
        *,
        input_type: str,
        payload: dict,
        client_request_id: str,
        conversation_id: int | None = None,
        turn_id: int | None = None,
        created_by: int | None = None,
        trace_id: str | None = None,
    ) -> AgentControlInput:
        if input_type not in ALLOWED_INPUT_TYPES:
            raise ControlInputError(f"未知控制输入类型：{input_type}")
        if not isinstance(payload, dict):
            raise ControlInputError("payload 必须是对象")

        existing = (
            AgentControlInput.query.filter_by(
                run_id=run.id, client_request_id=client_request_id
            ).first()
        )
        if existing is not None:
            return existing

        control = AgentControlInput(
            public_id=f"ctl-{uuid.uuid4().hex[:16]}",
            conversation_id=conversation_id,
            turn_id=turn_id,
            run_id=run.id,
            input_type=input_type,
            client_request_id=client_request_id,
            payload_json=payload,
            status="pending",
            created_by=created_by,
        )
        db.session.add(control)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            return (
                AgentControlInput.query.filter_by(
                    run_id=run.id, client_request_id=client_request_id
                ).one()
            )
        self._writer.emit(
            run,
            event_type=_EVENT_BY_INPUT_TYPE[input_type],
            item_id=control.public_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            payload=dict(payload),
            trace_id=trace_id,
        )
        db.session.commit()
        return control

    # ---------------------------------------------------------------- queries

    def list_pending(self, run_id: int) -> list[AgentControlInput]:
        """按确定性优先级返回未应用的控制输入。"""
        rows = (
            AgentControlInput.query.filter_by(
                run_id=run_id, status="pending"
            ).all()
        )
        return sorted(
            rows,
            key=lambda item: (
                _INPUT_TYPE_PRIORITY.get(item.input_type, 99),
                item.id,
            ),
        )

    def pending_by_type(self, run_id: int, input_type: str) -> list[AgentControlInput]:
        return [
            item
            for item in self.list_pending(run_id)
            if item.input_type == input_type
        ]

    # ---------------------------------------------------------------- lifecycle

    def apply(
        self,
        control: AgentControlInput,
        *,
        iteration: int,
        trace_id: str | None = None,
    ) -> AgentControlInput:
        if control.status in _TERMINAL_STATUSES:
            return control
        control.status = "applied"
        control.applied_iteration = iteration
        control.applied_at = datetime.utcnow()
        db.session.commit()
        return control

    def reject(
        self,
        control: AgentControlInput,
        *,
        trace_id: str | None = None,
    ) -> AgentControlInput:
        if control.status in _TERMINAL_STATUSES:
            return control
        control.status = "rejected"
        db.session.commit()
        return control

    def supersede(
        self,
        control: AgentControlInput,
        *,
        trace_id: str | None = None,
    ) -> AgentControlInput:
        if control.status in _TERMINAL_STATUSES:
            return control
        control.status = "superseded"
        db.session.commit()
        return control
