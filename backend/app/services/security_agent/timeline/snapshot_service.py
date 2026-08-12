# -*- coding: utf-8 -*-
"""Timeline SnapshotService（T03，spec §13.6）：固定水位一致快照与 Items 分页。

所有返回内容不超出 snapshot_watermark（run.last_event_sequence 读取时点）；
v2 客户端以 snapshot_watermark 作为 SSE Last-Event-ID 起点。
"""
from __future__ import annotations

from app import db
from app.models.agent_events import AgentEvent
from app.models.agent_items import AgentItem
from app.models.agent_runtime import AgentPlan, AgentRun


class SnapshotService:
    def build_snapshot(self, run_id: int) -> dict:
        """构建一致快照：run / plan / items / events + 固定水位。"""
        run = db.session.get(AgentRun, run_id)
        if run is None:
            raise ValueError(f"Run 不存在：{run_id}")
        watermark = int(run.last_event_sequence or 0)
        plan = (
            AgentPlan.query.filter_by(run_id=run_id)
            .order_by(AgentPlan.plan_version.desc())
            .first()
        )
        items = (
            AgentItem.query.filter_by(run_id=run_id)
            .order_by(AgentItem.id.asc())
            .all()
        )
        events = (
            AgentEvent.query.filter(
                AgentEvent.run_id == run_id,
                AgentEvent.sequence <= watermark,
            )
            .order_by(AgentEvent.sequence.asc())
            .all()
        )
        return {
            "run": run.to_dict(),
            "plan": plan.to_dict() if plan is not None else None,
            "items": [item.to_dict() for item in items],
            "events": [event.to_dict() for event in events],
            "snapshot_watermark": watermark,
            "last_sequence": watermark,
            "state_version": run.state_version,
        }

    def list_items(
        self,
        run_id: int,
        *,
        page: int = 1,
        page_size: int = 50,
        item_type: str | None = None,
    ) -> tuple[list[AgentItem], int]:
        """服务端分页 Items 查询（数据库分页，不 .all() 后切片）。"""
        query = AgentItem.query.filter_by(run_id=run_id)
        if item_type:
            query = query.filter_by(item_type=item_type)
        total = query.count()
        offset = max(0, page - 1) * page_size
        rows = (
            query.order_by(AgentItem.id.asc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return rows, total
