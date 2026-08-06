"""User-scoped persistent memory endpoints: list, delete."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.services.memory import service as memory_service

memories_bp = Blueprint("memories", __name__)


@memories_bp.route("/memories", methods=["GET"])
@jwt_required()
def list_memories():
    """分页列出当前用户的持久记忆。"""
    user_id = int(get_jwt_identity())
    try:
        items, total = memory_service.list_memories(user_id, request.args.to_dict())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "items": [
                {
                    **item.to_dict(),
                    "category_label": memory_service.category_label(item.category),
                }
                for item in items
            ],
            "total": total,
        }
    ), 200


@memories_bp.route("/memories/<int:memory_id>", methods=["DELETE"])
@jwt_required()
def delete_memory(memory_id: int):
    """删除当前用户的一条持久记忆。"""
    user_id = int(get_jwt_identity())
    if not memory_service.delete_memory(user_id, memory_id):
        return jsonify({"error": "记忆不存在"}), 404
    return jsonify({"deleted": True}), 200
