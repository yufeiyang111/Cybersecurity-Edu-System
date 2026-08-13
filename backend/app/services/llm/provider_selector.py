"""Select a user's private Provider while preserving existing fallbacks."""
from __future__ import annotations

from flask import current_app, has_app_context

from app.services.remediation.providers import select_configured_provider

from .call_logging import observe_provider
from .openai_compatible import OpenAICompatibleProvider
from .provider_service import get_default_for_user
from .secrets import decrypt_secret


def resolve_provider_max_tokens(provider: object, fallback: int) -> int:
    """优先使用用户在 Provider 配置里设置的 max_tokens，未配置时回退代码默认值。"""
    configured = getattr(provider, "max_tokens", None)
    if isinstance(configured, int) and configured > 0:
        return configured
    return fallback


def select_provider(user_id: int | None = None, operation: str = "unknown"):
    if user_id is not None and has_app_context():
        try:
            configured = get_default_for_user(user_id)
        except Exception as exc:
            # 用户 provider 查询失败（如迁移未应用、DB 不可用）时不得阻断
            # 系统兜底：记录后继续回退到 env 配置的服务端 provider
            current_app.logger.warning(
                "User LLM provider lookup failed, falling back to server provider (error_type=%s)",
                type(exc).__name__,
            )
            configured = None
        if configured is not None:
            try:
                provider = OpenAICompatibleProvider(
                    provider_name=configured.name,
                    base_url=configured.base_url,
                    api_key=decrypt_secret(configured.api_key_ciphertext),
                    model=configured.model,
                    provider_config_id=configured.id,
                    user_id=user_id,
                    operation=operation,
                    max_tokens=configured.max_tokens,
                )
                return observe_provider(provider, user_id=user_id, operation=operation)
            except (RuntimeError, ValueError):
                current_app.logger.warning(
                    "User LLM provider could not be loaded (provider_id=%s)",
                    configured.id,
                )
    try:
        # 服务端兜底：优先构造 OpenAI-compatible 的 minimax（/chat/completions
        # 支持 Agent 原生工具调用 + 流式 <think> 提取）；旧 MiniMaxProvider
        # 仅作为最后 fallback（无 agent 能力，agent 轮会退化为 JSON fallback，
        # 导致思考过程与原生工具调用全部丢失）。
        server = _server_openai_compatible_provider(user_id=user_id, operation=operation)
        if server is not None:
            return observe_provider(server, user_id=user_id, operation=operation)
        provider = select_configured_provider()
        if provider is not None and user_id is not None:
            return observe_provider(provider, user_id=user_id, operation=operation)
        return provider
    except RuntimeError:
        return None


def _server_openai_compatible_provider(
    user_id: int | None, operation: str
) -> OpenAICompatibleProvider | None:
    """按服务端 env 配置构造 OpenAI-compatible Provider（优先 minimax）。"""
    api_key = str(current_app.config.get("MINIMAX_API_KEY", "")).strip()
    if not api_key:
        return None
    return OpenAICompatibleProvider(
        provider_name="minimax",
        base_url=str(
            current_app.config.get("MINIMAX_API_BASE", "https://api.minimaxi.com/v1")
        ),
        api_key=api_key,
        model=str(current_app.config.get("MINIMAX_MODEL", "MiniMax-M2.7")).strip()
        or "MiniMax-M2.7",
        provider_config_id=None,
        user_id=user_id,
        operation=operation,
    )
