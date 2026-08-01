"""
认证相关工具函数
"""
from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from app.models.user import User, Role
import bcrypt


def hash_password(password: str) -> str:
    """密码哈希"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))

def generate_token(user_id, role):
    """生成JWT令牌"""
    from flask_jwt_extended import create_access_token
    return create_access_token(
        identity=user_id,
        additional_claims={"role": role}
    )


def issue_tokens(user):
    """统一签发 access/refresh token，供登录与 OAuth 登录复用"""
    from flask_jwt_extended import create_access_token, create_refresh_token
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            "username": user.username,
            "role": user.role.name if user.role else "guest",
        },
    )
    refresh_token = create_refresh_token(identity=user.id)
    return access_token, refresh_token

def verify_token(token):
    """验证JWT令牌"""
    from flask_jwt_extended import decode_token
    try:
        decoded = decode_token(token)
        return decoded
    except Exception:
        return None

def admin_required(fn):
    """管理员权限装饰器"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify({"error": "需要管理员权限"}), 403
        return fn(*args, **kwargs)
    return wrapper

def teacher_required(fn):
    """教师权限装饰器"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get("role") not in ["admin", "teacher"]:
            return jsonify({"error": "需要教师或管理员权限"}), 403
        return fn(*args, **kwargs)
    return wrapper

def get_current_user():
    """获取当前登录用户"""
    user_id = get_jwt_identity()
    if user_id:
        return User.query.get(user_id)
    return None

def check_permission(required_permission):
    """检查用户是否有指定权限"""
    claims = get_jwt()
    role = claims.get("role", "guest")
    
    if role == "admin":
        return True
    
    if role == "teacher":
        teacher_permissions = ["knowledge:create", "knowledge:edit", "knowledge:delete", "qa:review"]
        if required_permission in teacher_permissions:
            return True
    
    if role == "user":
        user_permissions = ["qa:ask", "qa:history", "favorite:manage", "knowledge:view"]
        if required_permission in user_permissions:
            return True
    
    if role == "guest" and required_permission == "knowledge:view":
        return True
    
    return False
