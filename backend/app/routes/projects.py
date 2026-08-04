"""Compatibility facade for the modular security workbench routes."""

from app.routes.security import projects_bp
from app.routes.security import knowledge as _knowledge_routes
from app.routes.security import projects as _project_routes
from app.routes.security import remediation as _remediation_routes
from app.routes.security import exclusions as _exclusion_routes
from app.routes.security import snapshots as _snapshot_routes
from app.routes.security import tasks as _task_routes
from app.routes.security import workbench as _workbench_routes
from app.routes.security import agent as _agent_routes

__all__ = ["projects_bp"]
