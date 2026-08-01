"""Security workbench route package with one shared public Blueprint."""

from flask import Blueprint

projects_bp = Blueprint("projects", __name__)

__all__ = ["projects_bp"]
