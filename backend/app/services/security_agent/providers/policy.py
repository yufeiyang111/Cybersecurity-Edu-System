# -*- coding: utf-8 -*-
"""工作区 Provider 策略（A8）：allowlist + 首选 Provider。

不保存 API Key/Base URL（密钥在用户配置与 env）；策略只约束"选谁"。
"""
from __future__ import annotations

from app import db
from app.models.security import Workspace

KNOWN_PROVIDERS = ("minimax", "dashscope", "deepseek-go", "openai")


class ProviderPolicyError(ValueError):
    pass


class WorkspaceProviderPolicy:
    def get(self, workspace: Workspace) -> dict:
        return {
            "allowlist": workspace.provider_allowlist or [],
            "preferred_provider": workspace.preferred_provider,
        }

    def update(
        self,
        workspace: Workspace,
        *,
        allowlist: list[str] | None,
        preferred_provider: str | None,
    ) -> Workspace:
        if allowlist is not None:
            if not isinstance(allowlist, list):
                raise ProviderPolicyError("allowlist 必须是数组")
            normalized = [str(item).strip().lower() for item in allowlist if str(item).strip()]
            unknown = [name for name in normalized if name not in KNOWN_PROVIDERS]
            if unknown:
                raise ProviderPolicyError(f"不支持的 Provider：{', '.join(unknown)}")
            workspace.provider_allowlist = normalized or None

        preferred = None
        if preferred_provider is not None:
            preferred = str(preferred_provider).strip().lower() or None
            if preferred and preferred not in KNOWN_PROVIDERS:
                raise ProviderPolicyError(f"不支持的 Provider：{preferred}")
            allow = workspace.provider_allowlist or []
            if preferred and allow and preferred not in allow:
                raise ProviderPolicyError("首选 Provider 必须在 allowlist 内")
        workspace.preferred_provider = preferred
        db.session.commit()
        return workspace

    def allows(self, workspace: Workspace, provider_name: str) -> bool:
        allow = workspace.provider_allowlist or []
        if not allow:
            return True
        return str(provider_name).strip().lower() in allow
