# -*- coding: utf-8 -*-
"""Agent Provider 路由与故障切换（A8）。

候选顺序：工作区首选（allowlist 校验）→ 用户配置 Provider → 服务端配置链。
generate_with_failover：首选失败时按候选链切换，每次切换发
strategy.switched 事件（reason_code=provider_failover）与安全日志；
全部失败返回 None（调用方自行降级）。不返回 API Key/Base URL。
"""
from __future__ import annotations

import logging

from app import db
from app.models.security import Workspace
from app.services.agent_observability import AgentLogger
from app.services.llm.provider_selector import select_provider
from app.services.remediation.providers import select_configured_provider
from app.services.security_agent.contracts import EVENT_STRATEGY_SWITCHED
from app.services.security_agent.event_service import EventService
from app.services.security_agent.providers.policy import WorkspaceProviderPolicy

logger = logging.getLogger(__name__)

FAILOVER_REASON = "provider_failover"


class AgentProviderRouter:
    def __init__(self, events: EventService | None = None) -> None:
        self._events = events or EventService()
        self._policy = WorkspaceProviderPolicy()
        self._agent_log = AgentLogger()

    # ------------------------------------------------------------------ candidates

    def candidates(
        self,
        *,
        user_id: int | None,
        workspace_id: int | None,
        operation: str,
    ) -> list[object]:
        """按策略顺序生成候选 Provider 列表（去重，允许空列表）。"""
        ordered: list[object] = []
        seen: set[str] = set()

        def _push(provider: object | None) -> None:
            if provider is None:
                return
            name = str(getattr(provider, "provider_name", "") or "").lower()
            if not name:
                return
            if name in seen:
                return
            seen.add(name)
            ordered.append(provider)

        workspace = (
            db.session.get(Workspace, workspace_id) if workspace_id else None
        )
        if workspace is not None and workspace.preferred_provider:
            if self._policy.allows(workspace, workspace.preferred_provider):
                preferred = _provider_by_name(
                    workspace.preferred_provider,
                    user_id=user_id,
                    operation=operation,
                )
                _push(preferred)

        _push(select_provider(user_id=user_id, operation=operation))
        _push(select_configured_provider())
        return ordered

    # ------------------------------------------------------------------ failover

    def generate_with_failover(
        self,
        *,
        run,
        candidates: list[object],
        request,
        trace_id: str | None,
        operation: str,
    ) -> tuple[object | None, object | None, list[dict]]:
        """逐个候选调用 provider.generate；返回 (response, provider, switches)。

        switches 形如 [{"from": name, "to": name, "reason": str}]，
        每次切换发出 strategy.switched 事件。
        """
        switches: list[dict] = []
        used: object | None = None
        for index, provider in enumerate(candidates):
            if index > 0:
                switches.append(
                    {
                        "from": str(getattr(candidates[index - 1], "provider_name", "unknown")),
                        "to": str(getattr(provider, "provider_name", "unknown")),
                        "reason": "首选 Provider 调用失败，切换备用",
                    }
                )
                self._events.emit(
                    run,
                    EVENT_STRATEGY_SWITCHED,
                    {
                        "reason_code": FAILOVER_REASON,
                        "from_provider": switches[-1]["from"],
                        "to_provider": switches[-1]["to"],
                        "operation": operation,
                    },
                    trace_id=trace_id,
                )
                self._agent_log.run_event(
                    "run.provider_failover",
                    run,
                    trace_id=trace_id,
                    from_provider=switches[-1]["from"],
                    to_provider=switches[-1]["to"],
                    operation=operation,
                )
            try:
                response = provider.generate(request)
            except Exception as exc:
                logger.warning(
                    "Agent provider %s call failed during failover (run_id=%s, error_type=%s)",
                    getattr(provider, "provider_name", "unknown"),
                    run.id,
                    type(exc).__name__,
                )
                db.session.rollback()
                continue
            if not response.is_success:
                logger.warning(
                    "Agent provider %s returned failure during failover (run_id=%s, warning=%s)",
                    getattr(provider, "provider_name", "unknown"),
                    run.id,
                    response.warning_code,
                )
                continue
            used = provider
            return response, used, switches
        return None, None, switches


def _provider_by_name(
    name: str, *, user_id: int | None, operation: str
) -> object | None:
    """按名称构造 provider（用户配置或服务端配置链）；不泄漏密钥。"""
    if name == "deepseek-go":
        return select_provider(user_id=user_id, operation=operation)
    from app.services.remediation.providers import create_configured_provider

    return create_configured_provider(name)


def get_agent_provider_router(events: EventService | None = None) -> AgentProviderRouter:
    return AgentProviderRouter(events)
