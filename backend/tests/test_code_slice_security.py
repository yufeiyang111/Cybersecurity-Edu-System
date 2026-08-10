"""Code slice security tests: path escape, symlink, oversized slices, boundary checks."""
from __future__ import annotations

import pytest

from app import db
from app.models.security import ProjectSnapshot, SecurityProject, Workspace, WorkspaceMember
from app.models.user import User
from app.services.project_security_graph.code_slice import (
    CodeSliceError,
    CodeSliceForbidden,
    read_code_slice,
    validate_slice_params,
)


def _make_snapshot(app, tmp_path):
    user = User(username="sliceuser", email="slice@t", password_hash="x")
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(name="sw", slug="sw-slice")
    db.session.add(workspace)
    db.session.flush()
    db.session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    )
    project = SecurityProject(workspace_id=workspace.id, name="sp", created_by=user.id)
    db.session.add(project)
    db.session.flush()
    root = tmp_path / "snap"
    root.mkdir(parents=True, exist_ok=True)
    (root / "app.py").write_text("\n".join(f"line{i}" for i in range(1, 51)), encoding="utf-8")
    snapshot = ProjectSnapshot(
        project_id=project.id,
        source_type="zip",
        content_sha256="sha-slice",
        storage_path=str(root),
        file_count=1,
        total_bytes=1,
    )
    db.session.add(snapshot)
    db.session.commit()
    return snapshot


def test_read_slice_success(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    payload = read_code_slice(snapshot, "app.py", 2, 4, "取证")
    assert payload["lines"] == ["line2", "line3", "line4"]


def test_read_slice_rejects_parent_escape(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("secret-content", encoding="utf-8")
    with pytest.raises(CodeSliceForbidden):
        read_code_slice(snapshot, "../secret.txt", 1, 2, "test")


def test_read_slice_rejects_absolute_path_escape(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    with pytest.raises(CodeSliceForbidden):
        read_code_slice(snapshot, str(tmp_path / "secret.txt"), 1, 2, "test")


def test_read_slice_rejects_symlink(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    root = tmp_path / "snap"
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link = root / "link.py"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("当前环境不支持创建符号链接")
    with pytest.raises(CodeSliceForbidden):
        read_code_slice(snapshot, "link.py", 1, 2, "test")


def test_read_slice_rejects_oversized_range(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    with pytest.raises(CodeSliceError):
        read_code_slice(snapshot, "app.py", 1, 300, "test")


def test_read_slice_rejects_end_beyond_file(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    with pytest.raises(CodeSliceError):
        read_code_slice(snapshot, "app.py", 40, 100, "test")


def test_read_slice_requires_reason(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    with pytest.raises(CodeSliceError):
        read_code_slice(snapshot, "app.py", 1, 2, "  ")


def test_read_slice_rejects_missing_file(app, tmp_path):
    snapshot = _make_snapshot(app, tmp_path)
    with pytest.raises(CodeSliceError):
        read_code_slice(snapshot, "nope.py", 1, 2, "test")


def test_validate_params_rejects_inverted_range():
    with pytest.raises(CodeSliceError):
        validate_slice_params(5, 2, "test")


def test_validate_params_rejects_zero_start():
    with pytest.raises(CodeSliceError):
        validate_slice_params(0, 2, "test")


def test_validate_params_rejects_missing_lines():
    with pytest.raises(CodeSliceError):
        validate_slice_params(None, 2, "test")


def test_validate_params_rejects_long_reason():
    with pytest.raises(CodeSliceError):
        validate_slice_params(1, 2, "r" * 201)
