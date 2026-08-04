"""Artifact persistence: large objects are stored once and referenced by summary."""
from __future__ import annotations

import hashlib
import json

from app import db
from app.models.agent_runtime import AgentArtifact, AgentRun

SENSITIVE_LEVELS = frozenset({"public", "internal", "sensitive"})


class ArtifactService:
    """Stores summary + optional small JSON content for agent artifacts."""

    def create(
        self,
        run: AgentRun,
        artifact_type: str,
        summary: str,
        *,
        content: dict | None = None,
        sensitive_level: str = "internal",
        plan_node_id: int | None = None,
        step_execution_id: int | None = None,
    ) -> AgentArtifact:
        if sensitive_level not in SENSITIVE_LEVELS:
            sensitive_level = "internal"
        content_hash = None
        if content is not None:
            content_hash = hashlib.sha256(
                json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
        artifact = AgentArtifact(
            run_id=run.id,
            plan_node_id=plan_node_id,
            step_execution_id=step_execution_id,
            artifact_type=artifact_type,
            summary=summary[:4000],
            content_hash=content_hash,
            content_json=content,
            sensitive_level=sensitive_level,
        )
        db.session.add(artifact)
        db.session.flush()
        return artifact
