# -*- coding: utf-8 -*-
"""Agent v2 Feature Flag 解析（spec §22.1，S-01/S-02/S-03）。

- 全局 env（AGENT_LOOP_V2_ENABLED / AGENT_EVENT_SCHEMA_V2_ENABLED /
  AGENT_TIMELINE_V2_ENABLED）是总开关；
- workspace 的 agent_feature_flags JSON 只能**降级**：把全局开启的能力在
  指定 workspace 关闭（灰度缩小范围）；全局关闭的能力不能被 workspace
  自行开启——未经授权的 workspace 无法开启高自治模式（deny by default）；
- 旧 Run 按创建时的协议读取，新建 Run 按解析结果选择协议。
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from flask import current_app

from app import db
from app.models.security import Workspace

FLAG_LOOP_V2 = "loop_v2"
FLAG_EVENT_SCHEMA_V2 = "event_schema_v2"
FLAG_TIMELINE_V2 = "timeline_v2"

AGENT_FEATURE_FLAG_KEYS = (FLAG_LOOP_V2, FLAG_EVENT_SCHEMA_V2, FLAG_TIMELINE_V2)

_ENV_TO_KEY = {
    FLAG_LOOP_V2: "AGENT_LOOP_V2_ENABLED",
    FLAG_EVENT_SCHEMA_V2: "AGENT_EVENT_SCHEMA_V2_ENABLED",
    FLAG_TIMELINE_V2: "AGENT_TIMELINE_V2_ENABLED",
}


@dataclass(frozen=True)
class AgentFlagSnapshot:
    """一次解析后的最终 flag 快照（全局 ∧ workspace 降级覆盖）。"""

    loop_v2: bool = False
    event_schema_v2: bool = False
    timeline_v2: bool = False

    def as_dict(self) -> dict:
        return {
            FLAG_LOOP_V2: self.loop_v2,
            FLAG_EVENT_SCHEMA_V2: self.event_schema_v2,
            FLAG_TIMELINE_V2: self.timeline_v2,
        }


class AgentFeatureFlags:
    """全局 env + workspace 降级覆盖解析；workspace 覆盖缓存短 TTL。"""

    CACHE_TTL_SECONDS = 60.0

    def __init__(self, app=None) -> None:
        self._app = app
        self._cache: dict[int, tuple[float, dict]] = {}

    def _global_values(self) -> dict:
        app = self._app or current_app
        values: dict = {}
        for key, env_name in _ENV_TO_KEY.items():
            values[key] = bool(app.config.get(env_name, False))
        return values

    def _workspace_overrides(self, workspace_id: int | None) -> dict:
        if not workspace_id:
            return {}
        now = time.monotonic()
        cached = self._cache.get(workspace_id)
        if cached is not None and now - cached[0] < self.CACHE_TTL_SECONDS:
            return cached[1]
        workspace = db.session.get(Workspace, workspace_id)
        overrides: dict = {}
        raw = getattr(workspace, "agent_feature_flags", None) if workspace is not None else None
        if isinstance(raw, dict):
            for key in AGENT_FEATURE_FLAG_KEYS:
                value = raw.get(key)
                if isinstance(value, bool):
                    overrides[key] = value
        self._cache[workspace_id] = (now, overrides)
        return overrides

    def invalidate(self, workspace_id: int | None = None) -> None:
        if workspace_id is None:
            self._cache.clear()
        else:
            self._cache.pop(workspace_id, None)

    def for_workspace(self, workspace_id: int | None) -> AgentFlagSnapshot:
        values = self._global_values()
        for key, disabled in self._workspace_overrides(workspace_id).items():
            # 覆盖只能降级：全局关闭时 workspace 无法开启。
            if disabled is False and values.get(key) is True:
                values[key] = False
        return AgentFlagSnapshot(**values)

    def for_run(self, run) -> AgentFlagSnapshot:
        workspace_id = getattr(run, "workspace_id", None)
        return self.for_workspace(workspace_id)


def resolve_agent_flags(app=None) -> AgentFeatureFlags:
    """模块级单例（缓存挂在其上；灰度变更后进程内最多延迟一个 TTL）。"""
    return AgentFeatureFlags(app)
