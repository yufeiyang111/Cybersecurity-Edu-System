# -*- coding: utf-8 -*-
"""
用户活跃统计路由

个人中心热力图数据源：
- qa：当前用户的问答记录（qa_records）按天计数
- tasks：当前用户所属工作区的 Agent 运行（agent_runs）与扫描任务（scan_tasks）按天计数
"""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models.qa import QARecord
from app.models.security import (
    WorkspaceMember,
    SecurityProject,
    ProjectSnapshot,
    ScanTask,
)
from app.models.agent_runtime import AgentRun

user_activity_bp = Blueprint("user_activity", __name__)

_ACTIVITY_WINDOW_DAYS = 366


def _count_by_day(query, column):
    """对已构建（含 join/filter）的查询按天分组计数"""
    rows = (
        query.with_entities(
            db.func.date(column).label("day"),
            db.func.count().label("count"),
        )
        .group_by("day")
        .all()
    )
    return [{"date": day, "count": count} for day, count in rows]


def _merge_daily_counts(*series):
    """合并多组按天计数（同日相加，按日期升序）"""
    merged = {}
    for items in series:
        for item in items:
            merged[item["date"]] = merged.get(item["date"], 0) + item["count"]
    return [
        {"date": day, "count": count}
        for day, count in sorted(merged.items())
    ]


@user_activity_bp.route("/activity", methods=["GET"])
@jwt_required()
def get_user_activity():
    user_id = get_jwt_identity()
    start = datetime.utcnow() - timedelta(days=_ACTIVITY_WINDOW_DAYS)

    qa = _count_by_day(
        QARecord.query.filter(
            QARecord.user_id == user_id,
            QARecord.created_at >= start,
        ),
        QARecord.created_at,
    )

    workspace_ids = [
        member.workspace_id
        for member in WorkspaceMember.query.filter_by(user_id=user_id).all()
    ]

    tasks = []
    if workspace_ids:
        agent_series = _count_by_day(
            AgentRun.query.filter(
                AgentRun.workspace_id.in_(workspace_ids),
                AgentRun.created_at >= start,
            ),
            AgentRun.created_at,
        )

        scan_series = _count_by_day(
            ScanTask.query.join(
                ProjectSnapshot,
                ScanTask.snapshot_id == ProjectSnapshot.id,
            ).join(
                SecurityProject,
                ProjectSnapshot.project_id == SecurityProject.id,
            ).filter(
                SecurityProject.workspace_id.in_(workspace_ids),
                ScanTask.created_at >= start,
            ),
            ScanTask.created_at,
        )

        tasks = _merge_daily_counts(agent_series, scan_series)

    return jsonify({"qa": qa, "tasks": tasks})
