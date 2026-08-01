"""
OAuth 第三方登录路由（Google / GitHub）

流程：前端跳转 authorize -> 跳转第三方授权 -> 回调换取 token ->
拉取用户资料 -> 查库/建用户 -> 签发本站 JWT -> 重定向回前端。
"""
import secrets
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, redirect
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


def _redirect_error(message):
    return redirect(f"{current_app.config['OAUTH_FRONTEND_URL']}/oauth/callback?error={quote(message)}")


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


@oauth_bp.route("/oauth/<provider>/authorize")
def oauth_authorize(provider):
    """发起第三方授权，重定向到 Google / GitHub。"""
    if provider not in _SUPPORTED_PROVIDERS:
        return jsonify({"error": "不支持的第三方登录方式"}), 400

    config = current_app.config
    client_id = config.get("GOOGLE_CLIENT_ID") if provider == "google" else config.get("GITHUB_CLIENT_ID")
    if not client_id:
        return jsonify({"error": f"{provider} 登录尚未配置，请联系管理员"}), 503

    client = getattr(oauth, provider)
    return client.authorize_redirect(_callback_url(provider))


@oauth_bp.route("/oauth/<provider>/callback")
def oauth_callback(provider):
    """第三方授权回调：换取 token、查库/建用户、签发本站 JWT。"""
    if provider not in _SUPPORTED_PROVIDERS:
        return _redirect_error("不支持的第三方登录方式")

    client = getattr(oauth, provider)
    try:
        client.authorize_access_token()
    except Exception as exc:
        current_app.logger.warning("OAuth(%s) 回调换取 token 失败: %s", provider, exc)
        return _redirect_error("授权失败，请重试")

    try:
        if provider == "google":
            info = client.get("userinfo").json()
            subject = str(info.get("sub") or "")
            email = info.get("email")
            nickname = info.get("name")
            avatar = info.get("picture")
        else:
            info = client.get("user").json()
            subject = str(info.get("id") or "")
            email = info.get("email")
            nickname = info.get("name") or info.get("login")
            avatar = info.get("avatar_url")
    except Exception as exc:
        current_app.logger.warning("OAuth(%s) 拉取用户信息失败: %s", provider, exc)
        return _redirect_error("获取第三方账号信息失败，请重试")

    if not subject:
        return _redirect_error("未获取到第三方账号标识")

    user = User.query.filter_by(oauth_provider=provider, oauth_subject=subject).first()

    if user is None and email:
        user = User.query.filter_by(email=email).first()
        if user:
            user.oauth_provider = provider
            user.oauth_subject = subject

    if user is None:
        user = _create_oauth_user(provider, subject, email, nickname, avatar)

    if not user.is_active:
        return _redirect_error("账号已被禁用")

    user.last_login_at = datetime.utcnow()
    db.session.commit()

    access_token, refresh_token = issue_tokens(user)
    return redirect(
        f"{current_app.config['OAUTH_FRONTEND_URL']}/oauth/callback"
        f"?token={access_token}&refresh={refresh_token}"
    )
