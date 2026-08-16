# -*- coding: utf-8 -*-
"""Harness V3 漏洞假设只读 API。"""
from __future__ import annotations

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.routes.security.agent.runs import _agent_run_or_404
from app.services.security_agent.hypotheses.query_service import HypothesisQueryService

from .. import projects_bp
from ..common import AuthorizationError

_service = HypothesisQueryService()


@projects_bp.route("/agent-runs/<int:run_id>/hypotheses", methods=["GET"])
@jwt_required()
def list_agent_run_hypotheses(run_id: int):
    """按数据库分页返回当前工作区可读的 V3 审计假设。"""
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 20, type=int)
        _service.validate_pagination(page=page, page_size=page_size)
        result = _service.list_for_run(run.id, page=page, page_size=page_size)
        return jsonify(
            {
                "items": [
                    _service.serialize_list_item(hypothesis)
                    for hypothesis in result.items
                ],
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
                "metrics": _service.metrics_for_run(run.id),
            }
        )
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@projects_bp.route(
    "/agent-runs/<int:run_id>/hypotheses/<int:hypothesis_id>",
    methods=["GET"],
)
@jwt_required()
def get_agent_run_hypothesis(run_id: int, hypothesis_id: int):
    """返回单条假设和其版本化 Critic 判定，跨 Run 查询不泄露存在性。"""
    try:
        run = _agent_run_or_404(run_id)
        if run is None:
            return jsonify({"error": "Agent 任务不存在"}), 404
        hypothesis = _service.get_for_run(run.id, hypothesis_id)
        if hypothesis is None:
            return jsonify({"error": "漏洞假设不存在"}), 404
        return jsonify({"hypothesis": _service.serialize_detail(hypothesis)})
    except AuthorizationError as exc:
        return jsonify({"error": str(exc)}), 403
