# -*- coding: utf-8 -*-
"""
管理员-索引重建任务接口（任务式 + 进度查询 + 量化报告）

支持三种重建模式（POST body 的 mode 字段）：
- "vector"：仅重建向量索引
- "graph" ：仅重建知识图谱（不触碰向量库）
- "all"   ：先向量后图谱（等价于旧的"重建所有索引"）

接口：
- POST /api/admin/vector/rebuild/task   启动后台重建任务
- GET  /api/admin/vector/rebuild/task   查询进度与完成后的量化报告
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt

from app.services.vector_rebuild_service import REBUILD_MODES, get_vector_rebuild_service

admin_vector_bp = Blueprint("admin_vector", __name__)


def _require_admin() -> bool:
    """检查是否为管理员（与 admin.py require_admin 保持一致）。"""
    claims = get_jwt()
    return claims.get("role", "guest") == "admin"


@admin_vector_bp.route("/vector/rebuild/task", methods=["POST"])
@jwt_required()
def start_vector_rebuild():
    """启动索引后台重建任务（向量 / 图谱 / 全部）。"""
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "vector")
    if mode not in REBUILD_MODES:
        return jsonify({"error": f"mode 必须是 {list(REBUILD_MODES)} 之一"}), 400

    service = get_vector_rebuild_service()
    result = service.start(mode=mode)
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
