"""Persistence models for the security scanning foundation."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from app import db


def _enum_values(enum_class: type[Enum]) -> list[str]:
    return [member.value for member in enum_class]


class WorkspaceMemberRole(str, Enum):
    OWNER = "owner"
    SECURITY_ADMIN = "security_admin"
    ANALYST = "analyst"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class ProjectSourceType(str, Enum):
    ZIP = "zip"
    GITHUB = "github"


class ScanTaskStatus(str, Enum):
    CREATED = "created"
    VALIDATING = "validating"
    SNAPSHOTTING = "snapshotting"
    SCANNING = "scanning"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CANCELED = "canceled"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(str, Enum):
    OPEN = "open"
    TRIAGED = "triaged"
    ACCEPTED_RISK = "accepted_risk"
    FALSE_POSITIVE = "false_positive"
    RESOLVED = "resolved"


class FindingCategory(str, Enum):
    SAST = "sast"
    SECRET = "secret"
    SCA = "sca"
    CONFIGURATION = "configuration"


class EvidenceType(str, Enum):
    CODE = "code"
    SECRET = "secret"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    RAG_REFERENCE = "rag_reference"


class RemediationReviewState(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class Workspace(db.Model):
    __tablename__ = "workspaces"
    __table_args__ = (
        db.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    provider_allowlist = db.Column(db.JSON)
    preferred_provider = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    members = db.relationship(
        "WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan"
    )
    projects = db.relationship(
        "SecurityProject", back_populates="workspace", cascade="all, delete-orphan"
    )
    audit_events = db.relationship("AuditEvent", back_populates="workspace")
    knowledge_sources = db.relationship(
        "SecurityKnowledgeSource", back_populates="workspace", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "provider_allowlist": self.provider_allowlist or [],
            "preferred_provider": self.preferred_provider,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WorkspaceMember(db.Model):
    __tablename__ = "workspace_members"
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership"),
        db.Index("ix_workspace_members_user_id", "user_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role = db.Column(
        db.Enum(
            WorkspaceMemberRole,
            name="workspace_member_role",
            values_callable=_enum_values,
        ),
        nullable=False,
        default=WorkspaceMemberRole.VIEWER.value,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace = db.relationship("Workspace", back_populates="members")
    user = db.relationship("User", back_populates="workspace_memberships")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "role": self.role.value if isinstance(self.role, Enum) else self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SecurityProject(db.Model):
    __tablename__ = "security_projects"
    __table_args__ = (
        db.UniqueConstraint("workspace_id", "name", name="uq_workspace_project_name"),
        db.Index("ix_security_projects_workspace_id", "workspace_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    default_branch = db.Column(db.String(255))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace = db.relationship("Workspace", back_populates="projects")
    creator = db.relationship("User", foreign_keys=[created_by])
    snapshots = db.relationship(
        "ProjectSnapshot", back_populates="project", cascade="all, delete-orphan"
    )
    exclusion_rules = db.relationship(
        "ProjectExclusionRule",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectExclusionRule.position",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "description": self.description,
            "default_branch": self.default_branch,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProjectExclusionRule(db.Model):
    """项目级 gitignore 风格扫描排除规则，按 position 顺序逐条匹配。"""

    __tablename__ = "project_exclusion_rules"
    __table_args__ = (
        db.UniqueConstraint("project_id", "position", name="uq_exclusion_rules_position"),
        db.Index("ix_exclusion_rules_project_id", "project_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("security_projects.id", ondelete="CASCADE"), nullable=False
    )
    pattern = db.Column(db.String(500), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    project = db.relationship("SecurityProject", back_populates="exclusion_rules")
    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pattern": self.pattern,
            "position": self.position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProjectSnapshot(db.Model):
    __tablename__ = "project_snapshots"
    __table_args__ = (
        db.UniqueConstraint("project_id", "content_sha256", name="uq_project_snapshot_content"),
        db.Index("ix_project_snapshots_project_id", "project_id"),
        db.Index("ix_project_snapshots_commit_sha", "commit_sha"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("security_projects.id", ondelete="CASCADE"), nullable=False
    )
    source_type = db.Column(
        db.Enum(ProjectSourceType, name="project_source_type", values_callable=_enum_values),
        nullable=False,
    )
    source_ref = db.Column(db.String(2048))
    commit_sha = db.Column(db.String(128))
    content_sha256 = db.Column(db.String(64), nullable=False)
    storage_path = db.Column(db.String(1024))
    file_count = db.Column(db.Integer, nullable=False, default=0)
    total_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project = db.relationship("SecurityProject", back_populates="snapshots")
    scan_tasks = db.relationship(
        "ScanTask", back_populates="snapshot", cascade="all, delete-orphan"
    )
    dependencies = db.relationship(
        "SnapshotDependency", back_populates="snapshot", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "source_type": self.source_type.value
            if isinstance(self.source_type, Enum)
            else self.source_type,
            "source_ref": self.source_ref,
            "commit_sha": self.commit_sha,
            "content_sha256": self.content_sha256,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SnapshotDependency(db.Model):
    """A normalized, non-sensitive dependency coordinate discovered in a snapshot."""

    __tablename__ = "snapshot_dependencies"
    __table_args__ = (
        db.UniqueConstraint(
            "snapshot_id",
            "coordinate_hash",
            name="uq_snapshot_dependency_coordinate",
        ),
        db.Index("ix_snapshot_dependencies_snapshot_id", "snapshot_id"),
        db.Index("ix_snapshot_dependencies_coordinate_hash", "coordinate_hash"),
    )

    id = db.Column(db.Integer, primary_key=True)
    snapshot_id = db.Column(
        db.Integer, db.ForeignKey("project_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    ecosystem = db.Column(db.String(64), nullable=False)
    package_name = db.Column(db.String(512), nullable=False)
    version = db.Column(db.String(255), nullable=False)
    manifest_path = db.Column(db.String(1024), nullable=False)
    coordinate_hash = db.Column(db.String(64), nullable=False)
    is_direct = db.Column(db.Boolean, nullable=False, default=True)
    source_line = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    snapshot = db.relationship("ProjectSnapshot", back_populates="dependencies")

    def to_dict(self) -> dict:
        """Expose only the normalized dependency inventory, never source content."""
        return {
            "id": self.id,
            "snapshot_id": self.snapshot_id,
            "ecosystem": self.ecosystem,
            "package_name": self.package_name,
            "version": self.version,
            "manifest_path": self.manifest_path,
            "is_direct": bool(self.is_direct),
            "source_line": self.source_line,
        }


class VulnerabilityAdvisoryCache(db.Model):
    """Cached third-party advisory responses keyed by a dependency coordinate."""

    __tablename__ = "vulnerability_advisory_cache"
    __table_args__ = (
        db.UniqueConstraint("cache_key", name="uq_vulnerability_advisory_cache_key"),
        db.Index("ix_vulnerability_advisory_cache_expires_at", "expires_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(128), nullable=False)
    ecosystem = db.Column(db.String(64), nullable=False)
    package_name = db.Column(db.String(512), nullable=False)
    version = db.Column(db.String(255), nullable=False)
    response_json = db.Column(db.JSON)
    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self) -> dict:
        """Return cache metadata without leaking an upstream advisory payload."""
        return {
            "id": self.id,
            "cache_key": self.cache_key,
            "coordinate": {
                "ecosystem": self.ecosystem,
                "package_name": self.package_name,
                "version": self.version,
            },
            "has_cached_response": self.response_json is not None,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class ScanTask(db.Model):
    __tablename__ = "scan_tasks"
    __table_args__ = (
        db.Index("ix_scan_tasks_snapshot_id", "snapshot_id"),
        db.Index("ix_scan_tasks_status", "status"),
        db.Index("ix_scan_tasks_created_at", "created_at"),
        db.Index("ix_scan_tasks_dispatch_key", "dispatch_key"),
        db.UniqueConstraint("dispatch_key", name="uq_scan_tasks_dispatch_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    snapshot_id = db.Column(
        db.Integer, db.ForeignKey("project_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    status = db.Column(
        db.Enum(ScanTaskStatus, name="scan_task_status", values_callable=_enum_values),
        nullable=False,
        default=ScanTaskStatus.CREATED.value,
    )
    progress = db.Column(db.Integer, nullable=False, default=0)
    policy_version = db.Column(db.String(100))
    exclusion_rules = db.Column(db.JSON)
    worker_id = db.Column(db.String(255))
    dispatch_key = db.Column(db.String(64), nullable=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    error_code = db.Column(db.String(100))
    error_message = db.Column(db.Text)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    canceled_at = db.Column(db.DateTime)
    summary_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    snapshot = db.relationship("ProjectSnapshot", back_populates="scan_tasks")
    findings = db.relationship(
        "SecurityFinding", back_populates="task", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "snapshot_id": self.snapshot_id,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "progress": self.progress,
            "policy_version": self.policy_version,
            "retry_count": self.retry_count,
            "can_retry": (self.status.value if isinstance(self.status, Enum) else self.status)
            in {ScanTaskStatus.FAILED.value, ScanTaskStatus.CANCELED.value},
            "can_cancel": (self.status.value if isinstance(self.status, Enum) else self.status)
            not in {
                ScanTaskStatus.COMPLETED.value,
                ScanTaskStatus.COMPLETED_WITH_WARNINGS.value,
                ScanTaskStatus.FAILED.value,
                ScanTaskStatus.CANCELED.value,
            },
            "error_code": self.error_code,
            "has_error": bool(self.error_code),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "canceled_at": self.canceled_at.isoformat() if self.canceled_at else None,
            "summary": self.summary_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SecurityFinding(db.Model):
    __tablename__ = "security_findings"
    __table_args__ = (
        db.UniqueConstraint("task_id", "fingerprint", name="uq_task_finding_fingerprint"),
        db.Index("ix_security_findings_task_id", "task_id"),
        db.Index("ix_security_findings_severity", "severity"),
        db.Index("ix_security_findings_status", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(
        db.Integer, db.ForeignKey("scan_tasks.id", ondelete="CASCADE"), nullable=False
    )
    fingerprint = db.Column(db.String(128), nullable=False)
    rule_id = db.Column(db.String(128), nullable=False)
    category = db.Column(
        db.Enum(FindingCategory, name="finding_category", values_callable=_enum_values),
        nullable=False,
    )
    severity = db.Column(
        db.Enum(FindingSeverity, name="finding_severity", values_callable=_enum_values),
        nullable=False,
    )
    status = db.Column(
        db.Enum(FindingStatus, name="finding_status", values_callable=_enum_values),
        nullable=False,
        default=FindingStatus.OPEN.value,
    )
    cwe_id = db.Column(db.String(32))
    cve_id = db.Column(db.String(32))
    file_path = db.Column(db.String(1024), nullable=False)
    start_line = db.Column(db.Integer, nullable=False)
    end_line = db.Column(db.Integer)
    message = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.Float)
    rule_version = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    task = db.relationship("ScanTask", back_populates="findings")
    evidences = db.relationship(
        "FindingEvidence", back_populates="finding", cascade="all, delete-orphan"
    )
    remediation_suggestions = db.relationship(
        "RemediationSuggestion", back_populates="finding", cascade="all, delete-orphan"
    )

    def to_dict(self, include_evidence: bool = False) -> dict:
        result = {
            "id": self.id,
            "task_id": self.task_id,
            "fingerprint": self.fingerprint,
            "rule_id": self.rule_id,
            "category": self.category.value if isinstance(self.category, Enum) else self.category,
            "severity": self.severity.value if isinstance(self.severity, Enum) else self.severity,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "cwe_id": self.cwe_id,
            "cve_id": self.cve_id,
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "message": self.message,
            "confidence": self.confidence,
            "rule_version": self.rule_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_evidence:
            result["evidence"] = [evidence.to_dict() for evidence in self.evidences]
        return result


class FindingEvidence(db.Model):
    __tablename__ = "finding_evidences"
    __table_args__ = (
        db.Index("ix_finding_evidences_finding_id", "finding_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    finding_id = db.Column(
        db.Integer, db.ForeignKey("security_findings.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type = db.Column(
        db.Enum(EvidenceType, name="evidence_type", values_callable=_enum_values),
        nullable=False,
    )
    content_redacted = db.Column(db.Text, nullable=False)
    secret_hash = db.Column(db.String(128))
    source_uri = db.Column(db.String(2048))
    start_line = db.Column(db.Integer)
    end_line = db.Column(db.Integer)
    score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    finding = db.relationship("SecurityFinding", back_populates="evidences")

    def to_dict(self) -> dict:
        """Return only display-safe evidence; full secret values are never persisted."""
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "type": self.evidence_type.value
            if isinstance(self.evidence_type, Enum)
            else self.evidence_type,
            "content": self.content_redacted,
            "source_uri": self.source_uri,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "score": self.score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AuditEvent(db.Model):
    __tablename__ = "audit_events"
    __table_args__ = (
        db.Index("ix_audit_events_workspace_created", "workspace_id", "created_at"),
        db.Index("ix_audit_events_target", "target_type", "target_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    action = db.Column(db.String(128), nullable=False)
    target_type = db.Column(db.String(128), nullable=False)
    target_id = db.Column(db.Integer)
    metadata_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace = db.relationship("Workspace", back_populates="audit_events")
    actor = db.relationship("User", foreign_keys=[actor_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "actor_id": self.actor_id,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "metadata": self.metadata_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }



class SecurityKnowledgeSource(db.Model):
    """Workspace-owned metadata for governed security knowledge."""

    __tablename__ = "security_knowledge_sources"
    __table_args__ = (
        db.Index("ix_security_knowledge_sources_workspace_active", "workspace_id", "is_active"),
    )

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(255), nullable=False)
    source_type = db.Column(db.String(64), nullable=False)
    source_uri = db.Column(db.String(2048))
    license_name = db.Column(db.String(255))
    source_version = db.Column(db.String(255), nullable=False)
    content_hash = db.Column(db.String(128))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    metadata_json = db.Column(db.JSON)
    published_at = db.Column(db.DateTime)
    effective_from = db.Column(db.DateTime)
    effective_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    workspace = db.relationship("Workspace", back_populates="knowledge_sources")
    documents = db.relationship(
        "SecurityKnowledgeDocument", back_populates="source", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Expose governed source metadata without arbitrary source metadata payloads."""
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "license_name": self.license_name,
            "source_version": self.source_version,
            "content_hash": self.content_hash,
            "is_active": bool(self.is_active),
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_until": self.effective_until.isoformat() if self.effective_until else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SecurityKnowledgeDocument(db.Model):
    """A versioned document belonging to exactly one workspace knowledge source."""

    __tablename__ = "security_knowledge_documents"
    __table_args__ = (
        db.UniqueConstraint("source_id", "document_version", name="uq_knowledge_source_document_version"),
        db.Index("ix_security_knowledge_documents_source_active", "source_id", "is_active"),
    )

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(
        db.Integer, db.ForeignKey("security_knowledge_sources.id", ondelete="CASCADE"), nullable=False
    )
    document_version = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    tags_json = db.Column(db.JSON)
    framework_metadata_json = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    effective_from = db.Column(db.DateTime)
    effective_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    source = db.relationship("SecurityKnowledgeSource", back_populates="documents")

    @property
    def workspace_id(self) -> int | None:
        """Resolve document ownership through its source rather than duplicate workspace data."""
        return self.source.workspace_id if self.source is not None else None

    def to_dict(self, include_content: bool = False) -> dict:
        """Content is opt-in; framework metadata stays internal to retrieval and governance logic."""
        result = {
            "id": self.id,
            "source_id": self.source_id,
            "document_version": self.document_version,
            "title": self.title,
            "summary": self.summary,
            "tags": self.tags_json or [],
            "is_active": bool(self.is_active),
            "effective_from": self.effective_from.isoformat() if self.effective_from else None,
            "effective_until": self.effective_until.isoformat() if self.effective_until else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_content:
            result["content"] = self.content
        return result


class RemediationSuggestion(db.Model):
    """Human-reviewable remediation output tied to one normalized security finding."""

    __tablename__ = "remediation_suggestions"
    __table_args__ = (
        db.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_remediation_suggestion_confidence"),
        db.Index("ix_remediation_suggestions_finding_created", "finding_id", "created_at"),
        db.Index("ix_remediation_suggestions_review_state", "review_state"),
    )

    id = db.Column(db.Integer, primary_key=True)
    finding_id = db.Column(
        db.Integer, db.ForeignKey("security_findings.id", ondelete="CASCADE"), nullable=False
    )
    rationale = db.Column(db.Text, nullable=False)
    remediation_steps_json = db.Column(db.JSON, nullable=False)
    patch_diff = db.Column(db.Text)
    citations_json = db.Column(db.JSON)
    warning_codes_json = db.Column(db.JSON)
    provider = db.Column(db.String(128), nullable=False)
    model = db.Column(db.String(255))
    model_version = db.Column(db.String(255))
    confidence = db.Column(db.Float)
    review_state = db.Column(
        db.Enum(
            RemediationReviewState,
            name="remediation_review_state",
            values_callable=_enum_values,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=RemediationReviewState.PENDING.value,
    )
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at = db.Column(db.DateTime)
    review_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    finding = db.relationship("SecurityFinding", back_populates="remediation_suggestions")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id])

    def to_dict(self) -> dict:
        """Return only reviewed remediation material, never provider prompts or raw responses."""
        return {
            "id": self.id,
            "finding_id": self.finding_id,
            "rationale": self.rationale,
            "remediation_steps": self.remediation_steps_json or [],
            "patch_diff": self.patch_diff,
            "citations": self.citations_json or [],
            "warning_codes": self.warning_codes_json or [],
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "confidence": self.confidence,
            "review_state": self.review_state.value
            if isinstance(self.review_state, Enum)
            else self.review_state,
            "reviewer_id": self.reviewer_id,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_comment": self.review_comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
