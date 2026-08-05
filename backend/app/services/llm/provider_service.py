"""User-scoped LLM provider validation and persistence operations."""
from __future__ import annotations

from datetime import datetime
from ipaddress import ip_address
from urllib.parse import urlsplit, urlunsplit

from app import db
from app.models.llm import LLMProviderConfig

from .secrets import encrypt_secret, mask_secret

SUPPORTED_PROVIDER_TYPE = "openai_compatible"
MAX_PROVIDER_NAME_LENGTH = 100
MAX_MODEL_LENGTH = 200
MAX_BASE_URL_LENGTH = 500
_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata.google.com",
    "instance-data.ec2.internal",
}


def validate_provider_url(value: str, *, allowed_hosts: list[str] | tuple[str, ...]) -> str:
    """Validate and normalize a user-provided outbound LLM endpoint."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Base URL 不能为空")
    raw = value.strip()
    if len(raw) > MAX_BASE_URL_LENGTH:
        raise ValueError("Base URL 长度超出限制")

    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Base URL 必须是无凭据的 HTTP 或 HTTPS 地址")
    if parsed.query or parsed.fragment:
        raise ValueError("Base URL 不能包含查询参数或 fragment")

    try:
        hostname = (parsed.hostname or "").strip().lower()
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Base URL 端口无效") from exc
    if not hostname:
        raise ValueError("Base URL 主机不能为空")

    host_key = f"{hostname}:{port}" if port is not None else hostname
    normalized_allowed = {_normalize_allowed_host(item) for item in allowed_hosts if str(item).strip()}
    explicitly_allowed = host_key in normalized_allowed or hostname in normalized_allowed

    if not explicitly_allowed and _is_blocked_hostname(hostname):
        raise ValueError("Base URL 主机不允许访问")
    if not explicitly_allowed and _is_restricted_ip(hostname):
        raise ValueError("Base URL 不能指向受限网络地址")
    if parsed.scheme == "http" and not explicitly_allowed:
        raise ValueError("HTTP 私有服务必须配置在 LLM_PROVIDER_ALLOWED_HOSTS 中")

    netloc = hostname
    if port is not None:
        netloc = f"{netloc}:{port}"
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, netloc, path, "", ""))


def list_for_user(user_id: int) -> list[LLMProviderConfig]:
    return (
        LLMProviderConfig.query.filter_by(user_id=user_id)
        .order_by(LLMProviderConfig.is_default.desc(), LLMProviderConfig.created_at.desc())
        .all()
    )


def get_for_user(provider_id: int, user_id: int) -> LLMProviderConfig | None:
    return LLMProviderConfig.query.filter_by(id=provider_id, user_id=user_id).first()


def get_default_for_user(user_id: int) -> LLMProviderConfig | None:
    return LLMProviderConfig.query.filter_by(
        user_id=user_id,
        is_default=True,
        is_enabled=True,
    ).first()


def create_for_user(user_id: int, data: dict, *, allowed_hosts: list[str] | tuple[str, ...]) -> LLMProviderConfig:
    values = _validated_values(data, allowed_hosts=allowed_hosts, require_api_key=True)
    existing = LLMProviderConfig.query.filter_by(user_id=user_id, name=values["name"]).first()
    if existing is not None:
        raise ValueError("同名 LLM 配置已存在")

    provider = LLMProviderConfig(user_id=user_id, **values)
    db.session.add(provider)
    db.session.flush()
    return provider


def update_for_user(
    provider: LLMProviderConfig,
    data: dict,
    *,
    allowed_hosts: list[str] | tuple[str, ...],
) -> LLMProviderConfig:
    values = _validated_values(
        data,
        allowed_hosts=allowed_hosts,
        require_api_key=False,
        existing=provider,
    )
    if values["name"] != provider.name:
        duplicate = LLMProviderConfig.query.filter(
            LLMProviderConfig.user_id == provider.user_id,
            LLMProviderConfig.name == values["name"],
            LLMProviderConfig.id != provider.id,
        ).first()
        if duplicate is not None:
            raise ValueError("同名 LLM 配置已存在")

    provider.name = values["name"]
    provider.provider_type = values["provider_type"]
    provider.base_url = values["base_url"]
    provider.model = values["model"]
    if values["api_key_ciphertext"] is not None:
        provider.api_key_ciphertext = values["api_key_ciphertext"]
        provider.api_key_hint = values["api_key_hint"]
    provider.is_enabled = values["is_enabled"]
    if "is_default" in data:
        provider.is_default = values["is_default"]
    db.session.flush()
    return provider


def delete_for_user(provider: LLMProviderConfig) -> None:
    db.session.delete(provider)
    db.session.flush()


def set_default(provider: LLMProviderConfig) -> LLMProviderConfig:
    LLMProviderConfig.query.filter(
        LLMProviderConfig.user_id == provider.user_id,
        LLMProviderConfig.id != provider.id,
    ).update({LLMProviderConfig.is_default: False}, synchronize_session=False)
    provider.is_default = True
    provider.is_enabled = True
    db.session.flush()
    return provider


def toggle_enabled(provider: LLMProviderConfig, enabled: bool | None = None) -> LLMProviderConfig:
    provider.is_enabled = not provider.is_enabled if enabled is None else _boolean(enabled, "is_enabled")
    if not provider.is_enabled:
        provider.is_default = False
    db.session.flush()
    return provider


def record_health_check(provider: LLMProviderConfig, status: str, latency_ms: int | None) -> None:
    provider.last_check_status = status[:32]
    provider.last_checked_at = datetime.utcnow()
    provider.last_latency_ms = latency_ms if isinstance(latency_ms, int) and latency_ms >= 0 else None
    db.session.flush()


def build_provider(
    provider: LLMProviderConfig,
    *,
    user_id: int,
    operation: str,
    http_client: object | None = None,
):
    from .openai_compatible import OpenAICompatibleProvider
    from .secrets import decrypt_secret

    return OpenAICompatibleProvider(
        provider_name=provider.name,
        base_url=provider.base_url,
        api_key=decrypt_secret(provider.api_key_ciphertext),
        model=provider.model,
        provider_config_id=provider.id,
        user_id=user_id,
        operation=operation,
        http_client=http_client,
    )


def _validated_values(
    data: dict,
    *,
    allowed_hosts: list[str] | tuple[str, ...],
    require_api_key: bool,
    existing: LLMProviderConfig | None = None,
) -> dict:
    if not isinstance(data, dict):
        raise ValueError("请求体必须是对象")
    name = data.get("name", existing.name if existing else None)
    model = data.get("model", existing.model if existing else None)
    base_url = data.get("base_url", existing.base_url if existing else None)
    provider_type = data.get("provider_type", SUPPORTED_PROVIDER_TYPE)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= MAX_PROVIDER_NAME_LENGTH:
        raise ValueError("name 长度必须在 1 至 100 个字符之间")
    if provider_type != SUPPORTED_PROVIDER_TYPE:
        raise ValueError("暂只支持 OpenAI 兼容 Provider")
    if not isinstance(model, str) or not 1 <= len(model.strip()) <= MAX_MODEL_LENGTH:
        raise ValueError("model 长度必须在 1 至 200 个字符之间")
    api_key = data.get("api_key")
    if require_api_key and (not isinstance(api_key, str) or not api_key.strip()):
        raise ValueError("API Key 不能为空")
    ciphertext = encrypt_secret(api_key) if isinstance(api_key, str) and api_key.strip() else None
    return {
        "name": name.strip(),
        "provider_type": provider_type,
        "base_url": validate_provider_url(base_url, allowed_hosts=allowed_hosts),
        "model": model.strip(),
        "api_key_ciphertext": ciphertext,
        "api_key_hint": mask_secret(api_key) if ciphertext else None,
        "is_enabled": _boolean(
            data["is_enabled"], "is_enabled"
        ) if "is_enabled" in data else (existing.is_enabled if existing else True),
        "is_default": _boolean(
            data["is_default"], "is_default"
        ) if "is_default" in data else (existing.is_default if existing else False),
    }


def _normalize_allowed_host(value: object) -> str:
    return str(value).strip().lower().rstrip("/")


def _is_blocked_hostname(hostname: str) -> bool:
    return hostname in _BLOCKED_HOSTNAMES or hostname.endswith(".localhost") or hostname.endswith(".local")


def _is_restricted_ip(hostname: str) -> bool:
    try:
        address = ip_address(hostname)
    except ValueError:
        return False
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是布尔值")
    return value
