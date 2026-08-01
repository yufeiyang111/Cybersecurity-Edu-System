"""Unit tests for snapshot creation application services."""
from __future__ import annotations

from flask import current_app


def test_github_policy_allows_exactly_one_archive_wrapper_directory(app) -> None:
    """GitHub zipball 只比普通 ZIP 多允许一层固定顶层目录。"""
    with app.app_context():
        from app.services.snapshot_service import archive_policy_from_settings, github_archive_policy

        upload_policy = archive_policy_from_settings(current_app.config)
        github_policy = github_archive_policy(current_app.config)

        assert github_policy.max_path_depth == upload_policy.max_path_depth + 1
        assert github_policy.max_archive_bytes == upload_policy.max_archive_bytes
        assert github_policy.max_extracted_bytes == upload_policy.max_extracted_bytes
        assert github_policy.max_file_count == upload_policy.max_file_count
