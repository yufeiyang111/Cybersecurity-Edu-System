# -*- coding: utf-8 -*-
"""
管理后台 - 用户详情路由

独立模块承载用户详情聚合查询，避免继续扩展巨型遗留模块 admin.py。
鉴权沿用 admin.py 的 require_admin 约定。
"""
from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import jwt_required, get_jwt

from app import db
from app.models.user import User, LoginLog
from app.models.qa import QARecord, QAConversation, Favorite
from app.models.security import WorkspaceMember
from app.models.memory import UserMemory

admin_users_bp = Blueprint("admin_users", __name__)


def _require_admin():
    """检查当前 JWT 是否为管理员"""
    claims = get_jwt()
    return claims.get("role") == "admin"


@admin_users_bp.route("/users/<int:user_id>/detail", methods=["GET"])
@jwt_required()
def get_user_detail(user_id):
    """获取用户详情（基础信息 + 使用统计 + 最近登录日志 + 最近问答）"""
    if not _require_admin():
        return jsonify({"error": "权限不足"}), 403

    user = User.query.get_or_404(user_id)

    qa_count = QARecord.query.filter_by(user_id=user_id).count()
    conversation_count = QAConversation.query.filter_by(user_id=user_id).count()
    favorite_count = Favorite.query.filter_by(user_id=user_id).count()
    workspace_count = (
        WorkspaceMember.query.filter_by(user_id=user_id).count()
        if current_app.config.get("SECURITY_WORKBENCH_ENABLED", True)
        else 0
    )
    memory_count = UserMemory.query.filter_by(user_id=user_id).count()

    login_logs = (
        LoginLog.query.filter_by(user_id=user_id)
        .order_by(LoginLog.login_time.desc())
        .limit(5)
        .all()
    )
    recent_records = (
        QARecord.query.filter_by(user_id=user_id)
        .order_by(QARecord.created_at.desc())
        .limit(5)
        .all()
    )

    return jsonify({
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "role": user.role.name if user.role else "guest",
            "is_active": user.is_active,
            "oauth_provider": user.oauth_provider,
            "oauth_bindings": user.get_oauth_bindings(),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        },
        "stats": {
            "qa_count": qa_count,
            "conversation_count": conversation_count,
            "favorite_count": favorite_count,
            "workspace_count": workspace_count,
            "memory_count": memory_count,
        },
        "login_logs": [
            {
                "id": log.id,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "status": log.status,
                "login_time": log.login_time.isoformat() if log.login_time else None,
            }
            for log in login_logs
        ],
        "recent_records": [
            {
                "id": record.id,
                "question": record.question,
                "feedback": record.feedback,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
            for record in recent_records
        ],
    }), 200
