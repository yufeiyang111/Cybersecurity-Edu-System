"""
用户认证路由
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    jwt_required, get_jwt_identity, get_jwt
)
from app import db
from app.models.user import User, Role
from app.utils.auth import verify_password, hash_password, issue_tokens
from app.services.rate_limit import rate_limit
from datetime import datetime

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
@rate_limit("auth-register", "SECURITY_RATE_LIMIT_PER_MINUTE")
def register():
    """用户注册"""
    data = request.get_json()
    
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()
    nickname = data.get("nickname", username)
    
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    
    if len(password) < 6:
        return jsonify({"error": "密码长度至少6位"}), 400
    
    # 检查用户是否已存在
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "用户名已存在"}), 400
    
    if email and User.query.filter_by(email=email).first():
        return jsonify({"error": "邮箱已被注册"}), 400
    
    # 获取默认角色
    default_role = Role.query.filter_by(name="user").first()
    
    # 创建用户
    user = User(
        username=username,
        password_hash=hash_password(password),
        email=email,
        nickname=nickname,
        role_id=default_role.id if default_role else None
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        "message": "注册成功",
        "user": user.to_dict()
    }), 201


@auth_bp.route("/login", methods=["POST"])
@rate_limit("auth-login", "SECURITY_EXPENSIVE_RATE_LIMIT_PER_MINUTE")
def login():
    """用户登录"""
    data = request.get_json()
    
    username = data.get("username", "")
    password = data.get("password", "")
    
    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not verify_password(password, user.password_hash):
        return jsonify({"error": "用户名或密码错误"}), 401
    
    if not user.is_active:
        return jsonify({"error": "账号已被禁用"}), 403
    
    # 更新登录时间
    user.last_login_at = datetime.utcnow()
    db.session.commit()

    # 创建 JWT token
    access_token, refresh_token = issue_tokens(user)
    
    return jsonify({
        "message": "登录成功",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user.to_dict()
    }), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """刷新 Token"""
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))  # 转换回整数

    if not user or not user.is_active:
        return jsonify({"error": "用户不存在或已禁用"}), 401

    access_token, _ = issue_tokens(user)
    
    return jsonify({
        "access_token": access_token,
        "user": user.to_dict()
    }), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    """获取当前用户信息"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    
    return jsonify({"user": user.to_dict()}), 200


@auth_bp.route("/me", methods=["PUT"])
@jwt_required()
def update_current_user():
    """更新当前用户信息"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    data = request.get_json()
    
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    
    # 可更新的字段
    if "nickname" in data:
        user.nickname = data["nickname"]
    if "email" in data:
        user.email = data["email"]
    if "avatar_url" in data:
        user.avatar_url = data["avatar_url"]
    if "password" in data:
        if len(data["password"]) < 6:
            return jsonify({"error": "密码长度至少6位"}), 400
        user.password_hash = hash_password(data["password"])
    
    db.session.commit()
    
    return jsonify({
        "message": "更新成功",
        "user": user.to_dict()
    }), 200


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    """修改密码"""
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    data = request.get_json()
    
    old_password = data.get("old_password", "")
    new_password = data.get("new_password", "")
    
    if not verify_password(old_password, user.password_hash):
        return jsonify({"error": "原密码错误"}), 400
    
    if len(new_password) < 6:
        return jsonify({"error": "新密码长度至少6位"}), 400
    
    user.password_hash = hash_password(new_password)
    db.session.commit()
    
    return jsonify({"message": "密码修改成功"}), 200
