"""Tool contracts shared by the tool registry and executor."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.models.agent_runtime import AgentPlanNode, AgentRun, AgentStepExecution, AgentToolCall

TOOL_RISK_LEVELS = frozenset(
    {"safe_read", "sensitive_read", "costly_external", "state_changing", "prohibited"}
)

AGENT_RUN_MODES = frozenset({"baseline", "hybrid", "deep_audit"})


@dataclass(frozen=True)
class ToolDescriptor:
    """Declarative contract for one deterministic tool.

    T05：安全关键字段缺省时注册失败（registry.register 调用 validate），
    不使用危险默认值；retry_policy 为 None 表示永不自动重试。
    """

    name: str
    version: str
    category: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "safe_read"
    timeout_seconds: int = 30
    idempotent: bool = True
    produces_artifact_types: list[str] = field(default_factory=list)
    requires_approval: bool = False
    retry_policy: dict[str, Any] | None = None
    allowed_modes: tuple[str, ...] = ("baseline", "hybrid", "deep_audit")
    result_schema_version: int = 1
    max_output_chars: int = 4000

    def validate(self) -> None:
        """注册前校验：非法值直接拒绝注册（拒绝危险默认值）。"""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("工具 name 必须是非空字符串")
        if self.risk_level not in TOOL_RISK_LEVELS:
            raise ValueError(f"未知风险等级：{self.risk_level}")
        if (
            not isinstance(self.timeout_seconds, int)
            or isinstance(self.timeout_seconds, bool)
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds 必须是正整数")
        if not isinstance(self.idempotent, bool):
            raise ValueError("idempotent 必须是布尔值")
        if not isinstance(self.requires_approval, bool):
            raise ValueError("requires_approval 必须是布尔值")
        if not self.allowed_modes or any(
            mode not in AGENT_RUN_MODES for mode in self.allowed_modes
        ):
            raise ValueError(
                f"allowed_modes 必须是非空模式白名单：{', '.join(sorted(AGENT_RUN_MODES))}"
            )
        if (
            not isinstance(self.result_schema_version, int)
            or isinstance(self.result_schema_version, bool)
            or self.result_schema_version < 1
        ):
            raise ValueError("result_schema_version 必须是正整数")
        if not isinstance(self.max_output_chars, int) or self.max_output_chars <= 0:
            raise ValueError("max_output_chars 必须是正整数")
        if self.retry_policy is not None:
            if not isinstance(self.retry_policy, dict):
                raise ValueError("retry_policy 必须是对象")
            max_attempts = self.retry_policy.get("max_attempts")
            if (
                not isinstance(max_attempts, int)
                or isinstance(max_attempts, bool)
                or max_attempts < 1
            ):
                raise ValueError("retry_policy.max_attempts 必须是正整数")
            codes = self.retry_policy.get("retryable_warning_codes")
            if codes is not None and (
                not isinstance(codes, list)
                or any(not isinstance(code, str) for code in codes)
            ):
                raise ValueError("retry_policy.retryable_warning_codes 必须是字符串列表")


@dataclass
class ToolExecutionContext:
    """Everything a tool needs to execute safely; identity is never guessed from HTTP state."""

    run: AgentRun
    plan_node: AgentPlanNode
    step_execution: AgentStepExecution
    tool_call: AgentToolCall
    workspace_id: int
    project_id: int
    snapshot_id: int
    actor_id: int | None
    trace_id: str | None
    deadline_epoch: float | None = None
    input: dict[str, Any] = field(default_factory=dict)

    def cancelled(self) -> bool:
        """Tools must poll this in loops; returns True once the run is canceled."""
        from app.models.agent_runtime import AgentRunStatus

        reloaded = AgentRun.query.filter_by(id=self.run.id).first()
        if reloaded is None:
            return True
        status = reloaded.status.value if hasattr(reloaded.status, "value") else reloaded.status
        return status in {
            AgentRunStatus.CANCEL_REQUESTED.value,
            AgentRunStatus.CANCELED.value,
        }


@dataclass
class ToolResult:
    """Normalized outcome of one tool invocation."""

    status: str = "succeeded"
    summary: str = ""
    artifact_refs: list[dict] = field(default_factory=list)
    warning_codes: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    retryable: bool = False

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "artifact_refs": self.artifact_refs,
            "warning_codes": self.warning_codes,
            "metrics": self.metrics,
            "error_code": self.error_code,
        }


ToolHandler = Callable[[ToolExecutionContext], ToolResult]


class ToolExecutionError(RuntimeError):
    """Raised by tools for expected, reportable failures (mapped to AGENT_TOOL_FAILED)."""

    def __init__(self, message: str, *, warning_code: str = "AGENT_TOOL_FAILED") -> None:
        super().__init__(message)
        self.warning_code = warning_code
