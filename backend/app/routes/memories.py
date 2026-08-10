"""User-scoped persistent memory endpoints: list, create, update, delete, feedback."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.models.memory import MemoryDreamAudit
from app.services.memory import service as memory_service
from app.services.rate_limit import rate_limit

memories_bp = Blueprint("memories", __name__)


def _serialize(user_id: int, item) -> dict:
    """序列化单条记忆：基础字段 + 分类标签 + 时间治理/反馈状态。"""
    negative = memory_service.negative_feedback_counts(user_id, [item.id])
    expires_at = item.expires_at
    is_expired = expires_at is not None and expires_at < datetime.utcnow()
    return {
        **item.to_dict(),
        "category_label": memory_service.category_label(item.category),
        "is_expired": bool(is_expired),
        "suggest_delete": negative.get(item.id, 0) >= memory_service.suggest_delete_threshold(),
        "negative_count": negative.get(item.id, 0),
    }


@memories_bp.route("/memories", methods=["GET"])
@jwt_required()
def list_memories():
    """分页列出当前用户的持久记忆（含过期与建议删除标注）。"""
    user_id = int(get_jwt_identity())
    try:
        items, total = memory_service.list_memories(user_id, request.args.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "items": [_serialize(user_id, item) for item in items],
            "total": total,
        }
    ), 200


@memories_bp.route("/memories", methods=["POST"])
@jwt_required()
def create_memory():
    """新增一条当前用户的持久记忆。"""
    user_id = int(get_jwt_identity())
    body = request.get_json(silent=True) or {}
    try:
        item = memory_service.create_memory(
            user_id,
            str(body.get("content") or ""),
            str(body.get("category") or "fact"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return (
        jsonify(
            {
                **item.to_dict(),
                "category_label": memory_service.category_label(item.category),
            }
        ),
        201,
    )


@memories_bp.route("/memories/<int:memory_id>", methods=["PUT"])
@jwt_required()
def update_memory(memory_id: int):
    """更新当前用户的一条持久记忆。"""
    user_id = int(get_jwt_identity())
    body = request.get_json(silent=True) or {}
    try:
        item = memory_service.update_memory(
            user_id,
            memory_id,
            str(body.get("content") or ""),
            str(body.get("category") or "fact"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if item is None:
        return jsonify({"error": "记忆不存在"}), 404
    return (
        jsonify(
            {
                **item.to_dict(),
                "category_label": memory_service.category_label(item.category),
            }
        ),
        200,
    )


@memories_bp.route("/memories/<int:memory_id>", methods=["DELETE"])
@jwt_required()
def delete_memory(memory_id: int):
    """删除当前用户的一条持久记忆。"""
    user_id = int(get_jwt_identity())
    if not memory_service.delete_memory(user_id, memory_id):
        return jsonify({"error": "记忆不存在"}), 404
    return jsonify({"deleted": True}), 200


@memories_bp.route("/memories/<int:memory_id>/feedback", methods=["POST"])
@jwt_required()
def feedback_memory(memory_id: int):
    """对一条记忆打标（0=没用 1=有用）；负面计数达标后管理页标注建议删除。"""
    user_id = int(get_jwt_identity())
    body = request.get_json(silent=True) or {}
    rating = body.get("rating")
    try:
        rating = int(rating) if rating is not None else -1
        memory, negative = memory_service.submit_feedback(user_id, memory_id, rating)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    if memory is None:
        return jsonify({"error": "记忆不存在"}), 404
    threshold = memory_service.suggest_delete_threshold()
    return jsonify(
        {
            "memory_id": memory.id,
            "rating": rating,
            "negative_count": negative,
            "suggest_delete": negative >= threshold,
        }
    ), 200


@memories_bp.route("/memories/dream", methods=["POST"])
@jwt_required()
@rate_limit("memory-dream", "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE")
def run_memory_dream():
    """对当前用户执行一轮 Dream 记忆整理（synthesize/supersede/merge）。"""
    user_id = int(get_jwt_identity())
    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run"))
    from app.services.memory import memory_dream

    result = memory_dream.run_dream(user_id=user_id, dry_run=dry_run)
    return jsonify(result), 200


@memories_bp.route("/memories/dream/audits", methods=["GET"])
@jwt_required()
def list_dream_audits():
    """最近 20 条 Dream 整理审计（仅当前用户）。"""
    user_id = int(get_jwt_identity())
    items = (
        MemoryDreamAudit.query.filter_by(user_id=user_id)
        .order_by(MemoryDreamAudit.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify(
        {
            "items": [
                {
                    "id": item.id,
                    "action": item.action,
                    "memory_ids": item.memory_ids,
                    "detail": item.detail,
                    "created_at": (
                        item.created_at.isoformat() if item.created_at else None
                    ),
                }
                for item in items
            ]
        }
    ), 200
