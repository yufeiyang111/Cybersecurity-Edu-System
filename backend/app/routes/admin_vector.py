# -*- coding: utf-8 -*-
"""
管理员-向量索引重建任务接口（任务式 + 进度查询 + 量化报告）

原 /admin/vector/rebuild 为同步阻塞接口（页面只能转圈等待）。
本模块提供：
- POST /api/admin/vector/rebuild/task   启动后台重建任务
- GET  /api/admin/vector/rebuild/task   查询进度与完成后的量化报告
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt

from app.services.vector_rebuild_service import get_vector_rebuild_service

admin_vector_bp = Blueprint("admin_vector", __name__)


def _require_admin() -> bool:
    """检查是否为管理员（与 admin.py require_admin 保持一致）。"""
    claims = get_jwt()
    return claims.get("role", "guest") == "admin"


@admin_vector_bp.route("/vector/rebuild/task", methods=["POST"])
@jwt_required()
def start_vector_rebuild():
    """启动向量索引后台重建任务（可选包含知识图谱）。"""
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

    data = request.get_json(silent=True) or {}
    include_graph = bool(data.get("include_graph", False))

    service = get_vector_rebuild_service()
    result = service.start(include_graph=include_graph)
    if result.get("busy"):
        return jsonify({"error": "已有重建任务正在运行，请等待其完成", "status": result}), 409
    return jsonify({"message": "重建任务已启动", "status": result}), 202


@admin_vector_bp.route("/vector/rebuild/task", methods=["GET"])
@jwt_required()
def get_vector_rebuild_status():
    """查询重建任务进度与量化报告。"""
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

    service = get_vector_rebuild_service()
    status = service.status()
    return jsonify({"status": status}), 200
