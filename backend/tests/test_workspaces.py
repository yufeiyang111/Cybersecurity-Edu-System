import pytest

from app import db
from app.models.security import Workspace, WorkspaceMember
from app.models.user import User
from app.services.workspaces import (
    AuthorizationError,
    get_or_create_personal_workspace,
    require_workspace_role,
)


def create_user(username: str, email: str) -> User:
    user = User(username=username, email=email, password_hash="x")
    db.session.add(user)
    db.session.commit()
    return user


def test_legacy_user_gets_one_personal_owner_workspace(app):
    with app.app_context():
        user = create_user("alice", "alice@example.test")
        first = get_or_create_personal_workspace(user.id)
        second = get_or_create_personal_workspace(user.id)

        assert first.id == second.id
        assert first.slug == f"personal-{user.id}"
        assert first.members[0].role == "owner"
        assert first.members[0].user_id == user.id


def test_member_cannot_access_unrelated_workspace(app):
    with app.app_context():
        user = create_user("alice", "alice@example.test")
        other_workspace = Workspace(name="Other", slug="other")
        db.session.add(other_workspace)
        db.session.commit()

        with pytest.raises(AuthorizationError, match="无权访问该工作区"):
            require_workspace_role(other_workspace.id, user.id, {"owner", "analyst"})


def test_viewer_cannot_access_analyst_or_security_admin_operations(app):
    with app.app_context():
        user = create_user("alice", "alice@example.test")
        workspace = Workspace(name="Security", slug="security")
        db.session.add(workspace)
        db.session.flush()
        db.session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="viewer")
        )
        db.session.commit()

        with pytest.raises(AuthorizationError, match="无权访问该工作区"):
            require_workspace_role(workspace.id, user.id, {"analyst", "security_admin"})
