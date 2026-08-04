"""Tool contracts shared by the tool registry and executor."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.models.agent_runtime import AgentPlanNode, AgentRun, AgentStepExecution, AgentToolCall

TOOL_RISK_LEVELS = frozenset(
    {"safe_read", "sensitive_read", "costly_external", "state_changing", "prohibited"}
)


@dataclass(frozen=True)
class ToolDescriptor:
    """Declarative contract for one deterministic tool."""

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
        return status == AgentRunStatus.CANCELED.value


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
