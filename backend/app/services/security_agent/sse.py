"""Replayable SSE stream over the durable AgentEvent table.

T10（spec §13.6/§13.7）：
- 事件 id = 持久化 sequence；event/data 与持久化 Event 一致，不在流层生成第二份语义；
- 正式 heartbeat 事件（event: heartbeat，不带 id，不占用 sequence），
  客户端可识别并刷新连接健康时间；
- Last-Event-ID 过旧（历史已归档）返回 AGENT_SSE_REPLAY_GAP 错误帧，
  客户端应重新拉取 Snapshot；
- terminal 且追平后关闭流；本模块绝不驱动 Agent。
"""
from __future__ import annotations

import json
import time

from flask import current_app
from sqlalchemy import func

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_runtime import AgentRun
from app.services.security_agent.state_machine import TERMINAL_STATUSES


def _event_lines(agent_event: AgentEvent) -> str:
    payload = {
        "run_id": agent_event.run_id,
        "sequence": agent_event.sequence,
        "state_version": agent_event.state_version,
        "event_type": agent_event.event_type,
        "occurred_at": agent_event.occurred_at.isoformat() if agent_event.occurred_at else None,
        "payload": agent_event.payload_json or {},
    }
    return (
        f"id: {agent_event.sequence}\n"
        f"event: {agent_event.event_type}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    )


def heartbeat_frame(sequence: int) -> str:
    """正式 heartbeat 事件：不携带 id（不占用 sequence），客户端可识别。"""
    return (
        "event: heartbeat\n"
        f"data: {json.dumps({'sequence': sequence}, ensure_ascii=False)}\n\n"
    )


def error_frame(code: str, message: str) -> str:
    return (
        "event: error\n"
        f"data: {json.dumps({'code': code, 'message': message}, ensure_ascii=False)}\n\n"
    )


def _min_sequence(run_id: int) -> int | None:
    value = (
        db.session.query(func.min(AgentEvent.sequence))
        .filter(AgentEvent.run_id == run_id)
        .scalar()
    )
    return int(value) if value is not None else None


def _record_sse_health(
    run: AgentRun, event_type: str, last_event_id: int
) -> None:
    """落一条 SSE 健康统计（spec §19.3 指标，迁移 037）。

    统计埋点失败绝不影响 SSE 流本身：记录安全结构化日志并回滚，
    不向客户端暴露任何内部信息。
    """
    from app.models.agent_sse import AgentSseHealth

    try:
        db.session.add(
            AgentSseHealth(
                workspace_id=run.workspace_id,
                run_id=run.id,
                event_type=event_type,
                last_event_id=max(0, int(last_event_id)),
            )
        )
        db.session.commit()
    except Exception as exc:  # noqa: BLE001 - 埋点必须隔离失败
        db.session.rollback()
        current_app.logger.warning(
            "sse health 埋点失败（run_id=%s, event_type=%s, error=%s）",
            run.id,
            event_type,
            type(exc).__name__,
        )


def agent_event_stream(
    run_id: int,
    last_event_id: int,
    *,
    heartbeat_seconds: int = 15,
    poll_seconds: float = 0.5,
) -> object:
    """Yield SSE frames for one agent run; used with flask Response + stream_with_context."""
    sequence = max(0, int(last_event_id or 0))

    run = db.session.get(AgentRun, run_id)
    if run is not None and sequence > 0:
        _record_sse_health(run, "connect_with_watermark", sequence)

    minimum = _min_sequence(run_id)
    if minimum is not None and sequence + 1 < minimum:
        if run is not None:
            _record_sse_health(run, "replay_gap", sequence)
        yield error_frame(
            "AGENT_SSE_REPLAY_GAP",
            "客户端水位过旧，历史事件已归档，请重新拉取 Snapshot",
        )
        return

    last_yield_epoch = time.monotonic()

    while True:
        try:
            with db.session() as session:
                events = (
                    session.query(AgentEvent)
                    .filter(AgentEvent.run_id == run_id, AgentEvent.sequence > sequence)
                    .order_by(AgentEvent.sequence.asc())
                    .limit(500)
                    .all()
                )
                for agent_event in events:
                    sequence = agent_event.sequence
                    yield _event_lines(agent_event)

                run = session.get(AgentRun, run_id)
                if run is None:
                    break
                status = run.status.value if hasattr(run.status, "value") else run.status
                caught_up = run.last_event_sequence <= sequence
                if status in TERMINAL_STATUSES and caught_up:
                    break
        finally:
            db.session.remove()

        now = time.monotonic()
        if now - last_yield_epoch >= heartbeat_seconds:
            yield heartbeat_frame(sequence)
            last_yield_epoch = now
        time.sleep(poll_seconds)
