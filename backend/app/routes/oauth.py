"""
OAuth 第三方登录路由（Google / GitHub）

两种流程：
1. 登录：前端跳转 authorize -> 第三方授权 -> 回调换取 token -> 查库/建用户 -> 签发本站 JWT。
2. 绑定：已登录用户在个人中心发起绑定，把 (provider, subject) 写入当前用户，下次可直接登录。

账号独立性：
- 第三方登录只按 (provider, subject) 匹配账号，不做邮箱自动合并；
- 自动建号时若邮箱已被占用则拒绝，避免与已有账号冲突。
"""
import secrets
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, redirect, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from authlib.integrations.flask_client import OAuth

from app import db
from app.models.user import User, Role
from app.utils.auth import issue_tokens

oauth = OAuth()
oauth_bp = Blueprint("oauth", __name__)

_SUPPORTED_PROVIDERS = ("google", "github")


def init_oauth(app):
    """在 app factory 中注册第三方 OAuth 客户端。"""
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID", ""),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET", ""),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        api_base_url="https://openidconnect.googleapis.com/v1",
        client_kwargs={"scope": "openid email profile"},
    )
    oauth.register(
        name="github",
        client_id=app.config.get("GITHUB_CLIENT_ID", ""),
        client_secret=app.config.get("GITHUB_CLIENT_SECRET", ""),
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "user:email"},
    )


def _callback_url(provider):
    return f"{current_app.config['OAUTH_BACKEND_BASE_URL']}/api/auth/oauth/{provider}/callback"


def _frontend_url(path):
    return f"{current_app.config['OAUTH_FRONTEND_URL']}{path}"


def _redirect_error(message):
    return redirect(_frontend_url(f"/oauth/callback?error={quote(message)}"))


def _provider_client_id(provider):
    config = current_app.config
    return config.get("GOOGLE_CLIENT_ID") if provider == "google" else config.get("GITHUB_CLIENT_ID")


def _create_oauth_user(provider, subject, email, nickname, avatar):
    default_role = Role.query.filter_by(name="user").first()
    base_username = f"{provider}_{subject}"[:50]
    username = base_username
    if User.query.filter_by(username=username).first():
        username = f"{base_username}_{secrets.token_hex(3)}"
    user = User(
        username=username,
        email=email,
        password_hash=None,
        nickname=nickname,
        avatar_url=avatar,
        oauth_provider=provider,
        oauth_subject=subject,
        role_id=default_role.id if default_role else None,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _fetch_identity(provider, client):
    """拉取第三方用户资料，返回 (subject, email, nickname, avatar)。"""
    if provider == "google":
        info = client.get("userinfo").json()
        return (
            str(info.get("sub") or ""),
            info.get("email"),
            info.get("name"),
            info.get("picture"),
        )
    info = client.get("user").json()
    return (
        str(info.get("id") or ""),
        info.get("email"),
        info.get("name") or info.get("login"),
        info.get("avatar_url"),
    )


def _handle_login(provider, subject, email, nickname, avatar):
    """第三方登录：按 (provider, subject) 匹配，未匹配则自动建号。"""
    user = User.query.filter_by(oauth_provider=provider, oauth_subject=subject).first()
    if user is None:
        if email:
            email_owner = User.query.filter_by(email=email).first()
            if email_owner:
                return _redirect_error("该邮箱已被注册，请使用该邮箱账号登录后绑定第三方账号")
        user = _create_oauth_user(provider, subject, email, nickname, avatar)

    if not user.is_active:
        return _redirect_error("账号已被禁用")

    user.last_login_at = datetime.utcnow()
    db.session.commit()

    access_token, refresh_token = issue_tokens(user)
    return redirect(
        _frontend_url(f"/oauth/callback?token={access_token}&refresh={refresh_token}")
    )


def _handle_bind(provider, subject, bind_user_id):
    """绑定：把第三方账号绑定到已登录的当前用户。"""
    existing = User.query.filter_by(oauth_provider=provider, oauth_subject=subject).first()
    if existing and str(existing.id) != str(bind_user_id):
        return _redirect_error("该第三方账号已绑定到其他账号")

    user = User.query.get(bind_user_id)
    if not user:
        return _redirect_error("账号不存在，请重新登录")

    user.oauth_provider = provider
    user.oauth_subject = subject
    db.session.commit()
    return redirect(_frontend_url(f"/user/profile?oauth_bind=ok&provider={provider}"))


@oauth_bp.route("/oauth/<provider>/authorize")
def oauth_authorize(provider):
    """发起第三方登录授权，重定向到 Google / GitHub。"""
    if provider not in _SUPPORTED_PROVIDERS:
        return jsonify({"error": "不支持的第三方登录方式"}), 400

    if not _provider_client_id(provider):
        return jsonify({"error": f"{provider} 登录尚未配置，请联系管理员"}), 503

    session.pop("oauth_bind_user_id", None)
    client = getattr(oauth, provider)
    return client.authorize_redirect(_callback_url(provider))


@oauth_bp.route("/oauth/<provider>/bind", methods=["POST"])
@jwt_required()
def oauth_bind(provider):
    """已登录用户发起第三方账号绑定，返回授权跳转地址。"""
    if provider not in _SUPPORTED_PROVIDERS:
        return jsonify({"error": "不支持的第三方登录方式"}), 400

    if not _provider_client_id(provider):
        return jsonify({"error": f"{provider} 登录尚未配置，请联系管理员"}), 503

    bind_user_id = get_jwt_identity()
    client = getattr(oauth, provider)
    callback_url = _callback_url(provider)
    authorization_url, state = client.create_authorization_url(callback_url)
    session[f"_oauth2_{provider}_authorization_state"] = state
    session["oauth_bind_user_id"] = bind_user_id
    return jsonify({"url": authorization_url}), 200


@oauth_bp.route("/oauth/<provider>/callback")
def oauth_callback(provider):
    """第三方授权回调：区分绑定与登录两种模式。"""
    if provider not in _SUPPORTED_PROVIDERS:
        return _redirect_error("不支持的第三方登录方式")

    client = getattr(oauth, provider)
    try:
        client.authorize_access_token()
    except Exception as exc:
        current_app.logger.warning("OAuth(%s) 回调换取 token 失败: %s", provider, exc)
        return _redirect_error("授权失败，请重试")

    try:
        subject, email, nickname, avatar = _fetch_identity(provider, client)
    except Exception as exc:
        current_app.logger.warning("OAuth(%s) 拉取用户信息失败: %s", provider, exc)
        return _redirect_error("获取第三方账号信息失败，请重试")

    if not subject:
        return _redirect_error("未获取到第三方账号标识")

    bind_user_id = session.pop("oauth_bind_user_id", None)
    if bind_user_id:
        return _handle_bind(provider, subject, bind_user_id)
    return _handle_login(provider, subject, email, nickname, avatar)
