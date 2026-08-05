"""Select a user's private Provider while preserving existing fallbacks."""
from __future__ import annotations

from flask import current_app, has_app_context

from app.services.remediation.providers import select_configured_provider

from .call_logging import observe_provider
from .openai_compatible import OpenAICompatibleProvider
from .provider_service import get_default_for_user
from .secrets import decrypt_secret


def select_provider(user_id: int | None = None, operation: str = "unknown"):
    if user_id is not None and has_app_context():
        configured = get_default_for_user(user_id)
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
                )
                return observe_provider(provider, user_id=user_id, operation=operation)
            except (RuntimeError, ValueError):
                current_app.logger.warning(
                    "User LLM provider could not be loaded (provider_id=%s)",
                    configured.id,
                )
    try:
        provider = select_configured_provider()
        if provider is not None and user_id is not None:
            return observe_provider(provider, user_id=user_id, operation=operation)
        return provider
    except RuntimeError:
        return None
