# -*- coding: utf-8 -*-
"""Agent Feature Flag 解析：全局默认、授权 workspace 覆盖与 Run 执行快照。"""
from __future__ import annotations

import time
from dataclasses import dataclass

from flask import current_app

from app import db
from app.models.security import Workspace

FLAG_LOOP_V2 = "loop_v2"
FLAG_EVENT_SCHEMA_V2 = "event_schema_v2"
FLAG_TIMELINE_V2 = "timeline_v2"
FLAG_HARNESS_V3 = "harness_v3"
FLAG_PROVIDER_RAW_REASONING_STREAM = "provider_raw_reasoning_stream"

AGENT_FEATURE_FLAG_KEYS = (
    FLAG_LOOP_V2,
    FLAG_EVENT_SCHEMA_V2,
    FLAG_TIMELINE_V2,
    FLAG_HARNESS_V3,
    FLAG_PROVIDER_RAW_REASONING_STREAM,
)

_ENV_TO_KEY = {
    FLAG_LOOP_V2: "AGENT_LOOP_V2_ENABLED",
    FLAG_EVENT_SCHEMA_V2: "AGENT_EVENT_SCHEMA_V2_ENABLED",
    FLAG_TIMELINE_V2: "AGENT_TIMELINE_V2_ENABLED",
    FLAG_HARNESS_V3: "AGENT_HARNESS_V3_ENABLED",
    FLAG_PROVIDER_RAW_REASONING_STREAM: "AGENT_PROVIDER_RAW_REASONING_STREAM_ENABLED",
}

# 新增高风险能力不能因历史快照缺字段而被意外开启。
_SNAPSHOT_ADDITIVE_SAFE_DEFAULTS = {
    FLAG_HARNESS_V3: False,
    FLAG_PROVIDER_RAW_REASONING_STREAM: False,
}


@dataclass(frozen=True)
class AgentFlagSnapshot:
    """一次解析后的最终 flag 快照（全局 env 被 workspace 授权覆盖）。"""

    loop_v2: bool = False
    event_schema_v2: bool = False
    timeline_v2: bool = False
    harness_v3: bool = False
    provider_raw_reasoning_stream: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            FLAG_LOOP_V2: self.loop_v2,
            FLAG_EVENT_SCHEMA_V2: self.event_schema_v2,
            FLAG_TIMELINE_V2: self.timeline_v2,
            FLAG_HARNESS_V3: self.harness_v3,
            FLAG_PROVIDER_RAW_REASONING_STREAM: self.provider_raw_reasoning_stream,
        }


class AgentFeatureFlags:
    """全局 env + workspace 授权覆盖解析；workspace 覆盖缓存短 TTL。"""

    CACHE_TTL_SECONDS = 60.0

    def __init__(self, app=None) -> None:
        self._app = app
        self._cache: dict[int, tuple[float, dict[str, bool]]] = {}

    def _global_values(self) -> dict[str, bool]:
        app = self._app or current_app
        return {
            key: bool(app.config.get(env_name, False))
            for key, env_name in _ENV_TO_KEY.items()
        }

    def _workspace_overrides(self, workspace_id: int | None) -> dict[str, bool]:
        if not workspace_id:
            return {}
        now = time.monotonic()
        cached = self._cache.get(workspace_id)
        if cached is not None and now - cached[0] < self.CACHE_TTL_SECONDS:
            return cached[1]
        workspace = db.session.get(Workspace, workspace_id)
        overrides: dict[str, bool] = {}
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
        # 授权覆盖双向生效：写入端已做 owner/security_admin 角色鉴权。
        values.update(self._workspace_overrides(workspace_id))
        return AgentFlagSnapshot(**values)

    def snapshot_for_run(self, run) -> AgentFlagSnapshot | None:
        """读取 Run 创建时快照；新增高风险能力缺失时按 false 兼容历史快照。"""
        raw_snapshot = getattr(run, "feature_flags_snapshot_json", None)
        if not isinstance(raw_snapshot, dict):
            return None

        values: dict[str, bool] = {}
        for key in AGENT_FEATURE_FLAG_KEYS:
            value = raw_snapshot.get(key)
            if isinstance(value, bool):
                values[key] = value
                continue
            if key in _SNAPSHOT_ADDITIVE_SAFE_DEFAULTS and key not in raw_snapshot:
                values[key] = _SNAPSHOT_ADDITIVE_SAFE_DEFAULTS[key]
                continue
            return None
        return AgentFlagSnapshot(**values)

    def for_run(self, run) -> AgentFlagSnapshot:
        """优先使用创建时快照，历史 Run 缺失快照时再兼容当前 workspace 配置。"""
        snapshot = self.snapshot_for_run(run)
        if snapshot is not None:
            return snapshot
        workspace_id = getattr(run, "workspace_id", None)
        return self.for_workspace(workspace_id)


def resolve_agent_flags(app=None) -> AgentFeatureFlags:
    """构造 Feature Flag 解析器；灰度变更在 workspace 缓存 TTL 后生效。"""
    return AgentFeatureFlags(app)