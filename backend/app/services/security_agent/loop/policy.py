# -*- coding: utf-8 -*-
"""Agent Loop 控制器策略（T01，spec §6.2/§6.3，v1.1 Reasoning Summary）。

策略是 Controller 的确定性快照：运行模式、循环限制、预算、租约心跳与
Reasoning Summary 上限。模型与工具都不能修改策略，只能读取。
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

AGENT_RUN_MODES_V2 = frozenset({"baseline", "hybrid", "deep_audit"})

DEFAULT_MAX_ITERATIONS = 20
DEFAULT_MAX_TOOL_CALLS = 30
DEFAULT_MAX_CONSECUTIVE_MODEL_ERRORS = 2
DEFAULT_MAX_SAME_TOOL_SAME_ARGS = 2
DEFAULT_MAX_PLAN_VERSIONS = 5
DEFAULT_MAX_CONTEXT_CHARS = 60000
DEFAULT_MAX_TOOL_RESULT_CHARS_PER_CALL = 12000
DEFAULT_LEASE_SECONDS = 60
DEFAULT_HEARTBEAT_SECONDS = 15
REASONING_SUMMARY_MAX_CHARS = 6000

_POSITIVE_INT_FIELDS = frozenset(
    {
        "max_iterations",
        "max_tool_calls",
        "max_consecutive_model_errors",
        "max_same_tool_same_args",
        "max_plan_versions",
        "max_context_chars",
        "max_tool_result_chars_per_call",
        "lease_seconds",
        "heartbeat_seconds",
        "reasoning_summary_max_chars",
    }
)


class PolicyValidationError(ValueError):
    """策略快照非法：未知模式、非正整数限制或未知字段。"""


@dataclass(frozen=True)
class AgentLoopPolicy:
    """Controller 策略快照；所有限制配置化并可序列化为 policy_snapshot_json。"""

    run_mode: str = "baseline"
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS
    max_consecutive_model_errors: int = DEFAULT_MAX_CONSECUTIVE_MODEL_ERRORS
    max_same_tool_same_args: int = DEFAULT_MAX_SAME_TOOL_SAME_ARGS
    max_plan_versions: int = DEFAULT_MAX_PLAN_VERSIONS
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS
    max_tool_result_chars_per_call: int = DEFAULT_MAX_TOOL_RESULT_CHARS_PER_CALL
    lease_seconds: int = DEFAULT_LEASE_SECONDS
    heartbeat_seconds: int = DEFAULT_HEARTBEAT_SECONDS
    reasoning_summary_max_chars: int = REASONING_SUMMARY_MAX_CHARS

    def __post_init__(self) -> None:
        if self.run_mode not in AGENT_RUN_MODES_V2:
            modes = "/".join(sorted(AGENT_RUN_MODES_V2))
            raise PolicyValidationError(f"运行模式必须是 {modes} 之一")
        for name in sorted(_POSITIVE_INT_FIELDS):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise PolicyValidationError(f"{name} 必须是正整数")

    def to_dict(self) -> dict:
        return {
            field.name: getattr(self, field.name)
            for field in dataclasses.fields(self)
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "AgentLoopPolicy":
        if not isinstance(raw, dict):
            raise PolicyValidationError("策略快照必须是对象")
        allowed = {field.name for field in dataclasses.fields(cls)}
        unknown = set(raw) - allowed
        if unknown:
            raise PolicyValidationError(f"策略包含未知字段：{', '.join(sorted(unknown))}")
        values: dict[str, Any] = {}
        for key in allowed:
            if key in raw:
                values[key] = raw[key]
        return cls(**values)
