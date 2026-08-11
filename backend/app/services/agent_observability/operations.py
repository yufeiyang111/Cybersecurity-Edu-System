# -*- coding: utf-8 -*-
"""A9 Agent 可观测性聚合：运行/工具/Provider/成本/审批一站式运维视图。

只读聚合，服务端分页；不暴露 Prompt、源码、密钥。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func

from app import db
from app.models.agent_approval import AgentApproval, ApprovalStatus
from app.models.agent_review import AgentObservation
from app.models.agent_runtime import AgentRun, AgentToolCall
from app.models.agent_llm import LLMInvocation


def observability_overview(*, workspace_id: int, days: int = 7) -> dict:
    """工作区 Agent 运维概览（状态分布/工具统计/成本/审批/观察）。"""
    since = datetime.utcnow() - timedelta(days=max(1, min(days, 90)))

    runs = AgentRun.query.filter(
        AgentRun.workspace_id == workspace_id,
        AgentRun.created_at >= since,
    ).all()
    status_counts: dict[str, int] = {}
    for run in runs:
        status = run.status.value if hasattr(run.status, "value") else str(run.status)
        status_counts[status] = status_counts.get(status, 0) + 1

    tool_stats = _tool_stats(workspace_id, since)
    cost_stats = _cost_stats(workspace_id, since)
    pending_approvals = (
        AgentApproval.query.filter_by(
            workspace_id=workspace_id, status=ApprovalStatus.PENDING.value
        ).count()
    )
    observation_count = (
        AgentObservation.query.join(AgentRun, AgentObservation.run_id == AgentRun.id)
        .filter(
            AgentRun.workspace_id == workspace_id,
            AgentObservation.created_at >= since,
        )
        .count()
    )

    return {
        "window_days": days,
        "run_counts": {
            "total": len(runs),
            "by_status": status_counts,
        },
        "tools": tool_stats,
        "llm": cost_stats,
        "pending_approvals": pending_approvals,
        "observations": observation_count,
    }


def observability_runs(
    *,
    workspace_id: int,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    mode: str | None = None,
) -> tuple[list[dict], int]:
    """运行列表（分页 + 状态/模式过滤）。"""
    query = AgentRun.query.filter_by(workspace_id=workspace_id)
    if status:
        query = query.filter(AgentRun.status == status)
    if mode:
        query = query.filter(AgentRun.mode == mode)
    total = query.count()
    page_size = min(max(1, page_size), 100)
    offset = max(0, page - 1) * page_size
    rows = query.order_by(AgentRun.id.desc()).offset(offset).limit(page_size).all()
    items = []
    for run in rows:
        item = run.to_dict()
        item["approval_pending"] = (
            AgentApproval.query.filter_by(
                run_id=run.id, status=ApprovalStatus.PENDING.value
            ).count()
            > 0
        )
        items.append(item)
    return items, total


def _tool_stats(workspace_id: int, since: datetime) -> dict:
    rows = (
        db.session.query(AgentToolCall.tool_name, AgentToolCall.status, func.count(AgentToolCall.id))
        .join(AgentRun, AgentToolCall.run_id == AgentRun.id)
        .filter(AgentRun.workspace_id == workspace_id, AgentToolCall.created_at >= since)
        .group_by(AgentToolCall.tool_name, AgentToolCall.status)
        .all()
    )
    by_tool: dict[str, dict] = {}
    for tool_name, status, count in rows:
        entry = by_tool.setdefault(
            tool_name, {"calls": 0, "succeeded": 0, "failed": 0, "latency_ms": None}
        )
        entry["calls"] += count
        if status == "succeeded":
            entry["succeeded"] += count
        else:
            entry["failed"] += count
    latency_rows = (
        db.session.query(
            AgentToolCall.tool_name,
            func.avg(AgentToolCall.latency_ms),
        )
        .join(AgentRun, AgentToolCall.run_id == AgentRun.id)
        .filter(
            AgentRun.workspace_id == workspace_id,
            AgentToolCall.created_at >= since,
            AgentToolCall.latency_ms.isnot(None),
        )
        .group_by(AgentToolCall.tool_name)
        .all()
    )
    for tool_name, avg_latency in latency_rows:
        if tool_name in by_tool and avg_latency is not None:
            by_tool[tool_name]["latency_ms"] = round(float(avg_latency), 1)
    return {
        "tools": [
            {"tool_name": name, **stats}
            for name, stats in sorted(by_tool.items(), key=lambda item: -item[1]["calls"])
        ][:20]
    }


def _cost_stats(workspace_id: int, since: datetime) -> dict:
    rows = (
        db.session.query(
            LLMInvocation.provider_name,
            func.count(LLMInvocation.id),
            func.sum(LLMInvocation.total_tokens),
            func.sum(LLMInvocation.total_cost),
        )
        .join(AgentRun, LLMInvocation.run_id == AgentRun.id)
        .filter(AgentRun.workspace_id == workspace_id, LLMInvocation.created_at >= since)
        .group_by(LLMInvocation.provider_name)
        .all()
    )
    providers = []
    total_cost = 0.0
    total_tokens = 0
    for provider_name, calls, tokens, cost in rows:
        providers.append(
            {
                "provider_name": provider_name,
                "calls": calls,
                "total_tokens": int(tokens or 0),
                "total_cost": round(float(cost or 0), 6),
            }
        )
        total_cost += float(cost or 0)
        total_tokens += int(tokens or 0)
    return {
        "providers": sorted(providers, key=lambda item: -item["total_cost"]),
        "total_cost": round(total_cost, 6),
        "total_tokens": total_tokens,
    }
