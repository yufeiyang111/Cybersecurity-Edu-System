"""Persistence models for the durable agent runtime (plan DAG, tools, artifacts)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from app import db


def _enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class AgentRunMode(str, Enum):
    BASELINE = "baseline"
    HYBRID = "hybrid"
    DEEP_AUDIT = "deep_audit"


class AgentRunStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    PREPARING = "preparing"
    MAPPING_REPOSITORY = "mapping_repository"
    PLANNING = "planning"
    VALIDATING_PLAN = "validating_plan"
    EXECUTING_TOOLS = "executing_tools"
    EVALUATING_EVIDENCE = "evaluating_evidence"
    REPLANNING = "replanning"
    DEEP_REVIEWING = "deep_reviewing"
    AWAITING_APPROVAL = "awaiting_approval"
    PAUSED = "paused"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELED = "canceled"


class AgentPlanNodeType(str, Enum):
    INVENTORY = "inventory"
    BASELINE_SCAN = "baseline_scan"
    COVERAGE_ANALYSIS = "coverage_analysis"
    REPOSITORY_MAPPING = "repository_mapping"
    RISK_RANKING = "risk_ranking"
    RAG_RETRIEVAL = "rag_retrieval"
    SEMANTIC_REVIEW = "semantic_review"
    HUMAN_APPROVAL = "human_approval"
    REMEDIATION_GENERATION = "remediation_generation"
    REPORT_GENERATION = "report_generation"


class AgentPlanNodeStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    CANCELED = "canceled"
    SUPERSEDED = "superseded"


class AgentPlanEdgeType(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CONDITION = "condition"
    ALWAYS = "always"
    EVIDENCE_GAP = "evidence_gap"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    BUDGET_AVAILABLE = "budget_available"


class AgentRun(db.Model):
    __tablename__ = "agent_runs"
    __table_args__ = (
        db.Index("ix_agent_runs_workspace_created", "workspace_id", "created_at"),
        db.Index("ix_agent_runs_status_lease", "status", "lease_expires_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("security_projects.id"), nullable=False)
    snapshot_id = db.Column(db.Integer, db.ForeignKey("project_snapshots.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    goal_text = db.Column(db.String(4000), nullable=False)
    mode = db.Column(
        db.Enum(AgentRunMode, name="agent_run_mode", values_callable=_enum_values),
        nullable=False,
        default=AgentRunMode.BASELINE.value,
    )
    status = db.Column(
        db.Enum(AgentRunStatus, name="agent_run_status", values_callable=_enum_values),
        nullable=False,
        default=AgentRunStatus.CREATED.value,
    )
    state_version = db.Column(db.Integer, nullable=False, default=0)
    plan_version = db.Column(db.Integer, nullable=False, default=0)
    planner_source = db.Column(db.String(64))
    last_event_sequence = db.Column(db.Integer, nullable=False, default=0)
    lease_owner = db.Column(db.String(255))
    lease_expires_at = db.Column(db.DateTime)
    heartbeat_at = db.Column(db.DateTime)
    tool_call_count = db.Column(db.Integer, nullable=False, default=0)
    llm_call_count = db.Column(db.Integer, nullable=False, default=0)
    input_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    cached_input_tokens = db.Column(db.Integer, nullable=False, default=0)
    reasoning_tokens = db.Column(db.Integer, nullable=False, default=0)
    total_tokens = db.Column(db.Integer, nullable=False, default=0)
    total_cost = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    currency = db.Column(db.String(8), nullable=False, default="USD")
    max_llm_calls = db.Column(db.Integer)
    max_tool_calls = db.Column(db.Integer)
    max_total_tokens = db.Column(db.Integer)
    max_estimated_cost = db.Column(db.Numeric(12, 6))
    max_wall_clock_seconds = db.Column(db.Integer)
    max_deep_review_files = db.Column(db.Integer)
    warning_codes = db.Column(db.JSON)
    error_code = db.Column(db.String(100))
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace = db.relationship("Workspace")
    project = db.relationship("SecurityProject")
    snapshot = db.relationship("ProjectSnapshot")
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self) -> dict:
        status = self.status.value if isinstance(self.status, Enum) else self.status
        mode = self.mode.value if isinstance(self.mode, Enum) else self.mode
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "snapshot_id": self.snapshot_id,
            "created_by": self.created_by,
            "goal_text": self.goal_text,
            "mode": mode,
            "status": status,
            "state_version": self.state_version,
            "plan_version": self.plan_version,
            "planner_source": self.planner_source,
            "last_event_sequence": self.last_event_sequence,
            "tool_call_count": self.tool_call_count,
            "llm_call_count": self.llm_call_count,
            "total_tokens": self.total_tokens,
            "total_cost": float(self.total_cost or 0),
            "currency": self.currency,
            "warning_codes": self.warning_codes or [],
            "error_code": self.error_code,
            "has_error": bool(self.error_code),
            "can_pause": status in PAUSABLE_RUN_STATUSES,
            "can_resume": status == AgentRunStatus.PAUSED.value,
            "can_cancel": status not in _TERMINAL_RUN_STATUSES,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


_TERMINAL_RUN_STATUSES = {
    AgentRunStatus.COMPLETED.value,
    AgentRunStatus.COMPLETED_WITH_WARNINGS.value,
    AgentRunStatus.PARTIAL.value,
    AgentRunStatus.FAILED.value,
    AgentRunStatus.CANCELED.value,
}

PAUSABLE_RUN_STATUSES = {
    AgentRunStatus.CREATED.value,
    AgentRunStatus.QUEUED.value,
    AgentRunStatus.PREPARING.value,
    AgentRunStatus.MAPPING_REPOSITORY.value,
    AgentRunStatus.PLANNING.value,
    AgentRunStatus.VALIDATING_PLAN.value,
    AgentRunStatus.EXECUTING_TOOLS.value,
    AgentRunStatus.EVALUATING_EVIDENCE.value,
    AgentRunStatus.REPLANNING.value,
    AgentRunStatus.DEEP_REVIEWING.value,
    AgentRunStatus.AWAITING_APPROVAL.value,
    AgentRunStatus.GENERATING_REPORT.value,
}


class AgentMessage(db.Model):
    __tablename__ = "agent_messages"
    __table_args__ = (
        db.Index("ix_agent_messages_run_created", "run_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id"), nullable=False)
    role = db.Column(db.String(32), nullable=False)
    content = db.Column(db.String(8000), nullable=False)
    message_type = db.Column(db.String(64), nullable=False, default="user_goal")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    run = db.relationship("AgentRun")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "role": self.role,
            "content": self.content,
            "message_type": self.message_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentPlan(db.Model):
    __tablename__ = "agent_plans"
    __table_args__ = (
        db.UniqueConstraint("run_id", "plan_version", name="uq_agent_plans_run_version"),
        db.Index("ix_agent_plans_run_id", "run_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id"), nullable=False)
    plan_version = db.Column(db.Integer, nullable=False)
    planner_source = db.Column(db.String(64), nullable=False)
    objective = db.Column(db.String(4000))
    decision_summary = db.Column(db.String(4000))
    hypotheses_json = db.Column(db.JSON)
    completion_criteria_json = db.Column(db.JSON)
    status = db.Column(db.String(32), nullable=False, default="created")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    run = db.relationship("AgentRun")
    nodes = db.relationship(
        "AgentPlanNode",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="AgentPlanNode.id",
    )
    edges = db.relationship(
        "AgentPlanEdge",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="AgentPlanEdge.id",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "plan_version": self.plan_version,
            "planner_source": self.planner_source,
            "objective": self.objective,
            "decision_summary": self.decision_summary,
            "hypotheses": self.hypotheses_json or [],
            "completion_criteria": self.completion_criteria_json or [],
            "status": self.status,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentPlanNode(db.Model):
    __tablename__ = "agent_plan_nodes"
    __table_args__ = (
        db.UniqueConstraint("plan_id", "node_key", name="uq_agent_plan_nodes_key"),
        db.Index("ix_agent_plan_nodes_plan_status", "plan_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("agent_plans.id"), nullable=False)
    node_key = db.Column(db.String(64), nullable=False)
    node_type = db.Column(
        db.Enum(AgentPlanNodeType, name="agent_plan_node_type", values_callable=_enum_values),
        nullable=False,
    )
    status = db.Column(
        db.Enum(AgentPlanNodeStatus, name="agent_plan_node_status", values_callable=_enum_values),
        nullable=False,
        default=AgentPlanNodeStatus.PENDING.value,
    )
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.String(4000))
    tool_name = db.Column(db.String(128))
    depends_on_json = db.Column(db.JSON)
    input_artifact_refs = db.Column(db.JSON)
    output_artifact_refs = db.Column(db.JSON)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    plan = db.relationship("AgentPlan", back_populates="nodes")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "node_key": self.node_key,
            "node_type": self.node_type.value if isinstance(self.node_type, Enum) else self.node_type,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "title": self.title,
            "description": self.description,
            "tool_name": self.tool_name,
            "depends_on": self.depends_on_json or [],
            "input_artifact_refs": self.input_artifact_refs or [],
            "output_artifact_refs": self.output_artifact_refs or [],
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AgentPlanEdge(db.Model):
    __tablename__ = "agent_plan_edges"
    __table_args__ = (
        db.Index("ix_agent_plan_edges_plan", "plan_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("agent_plans.id"), nullable=False)
    from_node = db.Column(db.String(64), nullable=False)
    to_node = db.Column(db.String(64), nullable=False)
    edge_type = db.Column(
        db.Enum(AgentPlanEdgeType, name="agent_plan_edge_type", values_callable=_enum_values),
        nullable=False,
        default=AgentPlanEdgeType.SUCCESS.value,
    )
    condition_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    plan = db.relationship("AgentPlan", back_populates="edges")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "edge_type": self.edge_type.value if isinstance(self.edge_type, Enum) else self.edge_type,
            "condition": self.condition_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentStepExecution(db.Model):
    __tablename__ = "agent_step_executions"
    __table_args__ = (
        db.UniqueConstraint("plan_node_id", "attempt_number", name="uq_agent_steps_attempt"),
        db.Index("ix_agent_steps_run_id", "run_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_node_id = db.Column(db.Integer, db.ForeignKey("agent_plan_nodes.id"), nullable=False)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id"), nullable=False)
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    worker_id = db.Column(db.String(255))
    status = db.Column(db.String(32), nullable=False, default="running")
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    retry_reason = db.Column(db.String(500))
    input_artifact_refs = db.Column(db.JSON)
    output_artifact_refs = db.Column(db.JSON)
    warning_codes = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    node = db.relationship("AgentPlanNode")
    run = db.relationship("AgentRun")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "plan_node_id": self.plan_node_id,
            "run_id": self.run_id,
            "attempt_number": self.attempt_number,
            "worker_id": self.worker_id,
            "status": self.status,
            "node_key": self.node.node_key if self.node is not None else None,
            "tool_name": self.node.tool_name if self.node is not None else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "retry_reason": self.retry_reason,
            "input_artifact_refs": self.input_artifact_refs or [],
            "output_artifact_refs": self.output_artifact_refs or [],
            "warning_codes": self.warning_codes or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentToolCall(db.Model):
    __tablename__ = "agent_tool_calls"
    __table_args__ = (
        db.UniqueConstraint("idempotency_key", name="uq_agent_tool_calls_idempotency"),
        db.Index("ix_agent_tool_calls_run_status", "run_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id"), nullable=False)
    plan_node_id = db.Column(db.Integer, db.ForeignKey("agent_plan_nodes.id"))
    step_execution_id = db.Column(db.Integer, db.ForeignKey("agent_step_executions.id"))
    tool_name = db.Column(db.String(128), nullable=False)
    tool_version = db.Column(db.String(64))
    status = db.Column(db.String(32), nullable=False, default="running")
    risk_level = db.Column(db.String(32), nullable=False, default="safe_read")
    idempotency_key = db.Column(db.String(255), nullable=False)
    input_summary = db.Column(db.String(4000))
    output_summary = db.Column(db.String(4000))
    artifact_refs = db.Column(db.JSON)
    warning_codes = db.Column(db.JSON)
    error_code = db.Column(db.String(100))
    latency_ms = db.Column(db.Integer)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    run = db.relationship("AgentRun")
    node = db.relationship("AgentPlanNode")
    step_execution = db.relationship("AgentStepExecution")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "plan_node_id": self.plan_node_id,
            "step_execution_id": self.step_execution_id,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "status": self.status,
            "risk_level": self.risk_level,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "artifact_refs": self.artifact_refs or [],
            "warning_codes": self.warning_codes or [],
            "error_code": self.error_code,
            "latency_ms": self.latency_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentArtifact(db.Model):
    __tablename__ = "agent_artifacts"
    __table_args__ = (
        db.Index("ix_agent_artifacts_run_type", "run_id", "artifact_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id"), nullable=False)
    plan_node_id = db.Column(db.Integer, db.ForeignKey("agent_plan_nodes.id"))
    step_execution_id = db.Column(db.Integer, db.ForeignKey("agent_step_executions.id"))
    artifact_type = db.Column(db.String(64), nullable=False)
    summary = db.Column(db.String(4000), nullable=False)
    content_hash = db.Column(db.String(64))
    content_json = db.Column(db.JSON)
    sensitive_level = db.Column(db.String(32), nullable=False, default="internal")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    run = db.relationship("AgentRun")

    def to_dict(self) -> dict:
        """Return metadata only; full content is opt-in through dedicated endpoints."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "plan_node_id": self.plan_node_id,
            "step_execution_id": self.step_execution_id,
            "artifact_type": self.artifact_type,
            "summary": self.summary,
            "content_hash": self.content_hash,
            "sensitive_level": self.sensitive_level,
            "has_content": self.content_json is not None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentCheckpoint(db.Model):
    __tablename__ = "agent_checkpoints"
    __table_args__ = (
        db.Index("ix_agent_checkpoints_run_created", "run_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("agent_runs.id"), nullable=False)
    plan_version = db.Column(db.Integer, nullable=False)
    state_json = db.Column(db.JSON, nullable=False)
    event_sequence = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    run = db.relationship("AgentRun")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "plan_version": self.plan_version,
            "state": self.state_json or {},
            "event_sequence": self.event_sequence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
