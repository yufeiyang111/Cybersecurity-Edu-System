"""Workspace bootstrap and authorization helpers for security resources."""
from __future__ import annotations

from app import db
from app.models.security import Workspace, WorkspaceMember, WorkspaceMemberRole
from app.models.user import User


class AuthorizationError(PermissionError):
    """Raised when a user is not authorized for a workspace resource."""

    def __init__(self) -> None:
        super().__init__("无权访问该工作区")


def _role_value(role: WorkspaceMemberRole | str) -> str:
    return role.value if isinstance(role, WorkspaceMemberRole) else str(role)


def get_or_create_personal_workspace(user_id: int) -> Workspace:
    """Return the deterministic default workspace for an existing user."""
    user = db.session.get(User, user_id)
    if user is None:
        raise ValueError("用户不存在")

    slug = f"personal-{user_id}"
    workspace = Workspace.query.filter_by(slug=slug).one_or_none()
    if workspace is not None:
        return workspace

    workspace = Workspace(name=f"{user.username} 的安全工作区", slug=slug)
    db.session.add(workspace)
    db.session.flush()
    db.session.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceMemberRole.OWNER.value,
        )
    )
    db.session.commit()
    return workspace


def get_workspace_member(workspace_id: int, user_id: int) -> WorkspaceMember | None:
    """Return the membership for a user in the requested workspace, if any."""
    return WorkspaceMember.query.filter_by(
        workspace_id=workspace_id,
        user_id=user_id,
    ).one_or_none()


def require_workspace_role(
    workspace_id: int,
    user_id: int,
    allowed_roles: set[str],
) -> WorkspaceMember:
    """Require a workspace membership role without leaking resource existence."""
    membership = get_workspace_member(workspace_id, user_id)
    role = _role_value(membership.role) if membership is not None else ""
    if membership is None or role not in {_role_value(item) for item in allowed_roles}:
        raise AuthorizationError()
    return membership
