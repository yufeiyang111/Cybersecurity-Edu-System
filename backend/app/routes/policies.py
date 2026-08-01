"""
政策文档路由（薄层）：公开读取 + 管理员更新
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app import db
from app.models.user import User
from app.services import policy_service

policies_bp = Blueprint("policies", __name__)


def _require_admin() -> bool:
    claims = get_jwt()
    return claims.get("role", "guest") == "admin"


@policies_bp.route("/policies", methods=["GET"])
def list_policies():
    """公开列出政策文档（不含正文）"""
    documents = policy_service.list_policies()
    return jsonify({
        "policies": [doc.to_dict(include_content=False) for doc in documents]
    }), 200


@policies_bp.route("/policies/<slug>", methods=["GET"])
def get_policy(slug: str):
    """公开读取单篇政策文档"""
    policy = policy_service.get_policy(slug)
    if policy is None:
        return jsonify({"error": "政策文档不存在"}), 404
    return jsonify({"policy": policy.to_dict()}), 200


@policies_bp.route("/policies/<slug>", methods=["PUT"])
@jwt_required()
def update_policy(slug: str):
    """管理员更新政策文档，保存时版本自增"""
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()

    if not title:
        return jsonify({"error": "标题不能为空"}), 400
    if len(title) > 200:
        return jsonify({"error": "标题长度不能超过 200 个字符"}), 400
    if not content:
        return jsonify({"error": "正文内容不能为空"}), 400

    policy = policy_service.get_policy(slug)
    if policy is None:
        return jsonify({"error": "政策文档不存在"}), 404

    identity = get_jwt_identity()
    updater = db.session.get(User, int(identity)) if identity and str(identity).isdigit() else None
    updated_by = updater.username if updater else str(identity)

    updated = policy_service.update_policy(slug, title, content, updated_by)
    return jsonify({"message": "政策文档更新成功", "policy": updated.to_dict()}), 200
