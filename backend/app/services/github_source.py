"""Fixed-host, read-only intake for public GitHub repository archives.

This adapter intentionally accepts only canonical public GitHub repository URLs. It
never invokes Git and it does not follow network redirects automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from urllib.parse import urlsplit

import requests


_GITHUB_WEB_HOST = "github.com"
_GITHUB_API_HOST = "api.github.com"
_GITHUB_CODELOAD_HOST = "codeload.github.com"
_GITHUB_API_BASE_URL = f"https://{_GITHUB_API_HOST}"
_COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
_OWNER_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class GitHubSourceError(RuntimeError):
    """Raised when a public GitHub archive cannot be safely retrieved."""


@dataclass(frozen=True)
class GitHubRepositoryRef:
    owner: str
    repository: str
    normalized_url: str
    ref: str | None = None


@dataclass(frozen=True)
class GitHubArchiveMetadata:
    repository: GitHubRepositoryRef
    source_ref: str
    default_branch: str
    commit_sha: str
    archive_path: Path
    archive_bytes: int


def parse_public_github_url(url: str) -> GitHubRepositoryRef:
    """Validate a canonical GitHub repository URL without resolving user hosts."""
    if not isinstance(url, str) or not url or url != url.strip():
        raise GitHubSourceError("GitHub 仓库地址无效")

    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise GitHubSourceError("GitHub 仓库地址无效") from exc

    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != _GITHUB_WEB_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise GitHubSourceError("GitHub 仓库地址无效")

    path = parsed.path
    if not path.startswith("/") or "%" in path or "\\" in path:
        raise GitHubSourceError("GitHub 仓库地址无效")

    path_without_optional_trailing_slash = path[:-1] if path.endswith("/") else path
    parts = path_without_optional_trailing_slash.split("/")
    if len(parts) != 3 or parts[0] != "":
        raise GitHubSourceError("GitHub 仓库地址无效")

    owner, repository = parts[1:]
    if (
        not _OWNER_PATTERN.fullmatch(owner)
        or not _REPOSITORY_PATTERN.fullmatch(repository)
        or repository.lower().endswith(".git")
    ):
        raise GitHubSourceError("GitHub 仓库地址无效")

    return GitHubRepositoryRef(
        owner=owner,
        repository=repository,
        normalized_url=f"https://{_GITHUB_WEB_HOST}/{owner}/{repository}",
        ref=None,
    )


def download_public_github_archive(
    repository_url: str,
    destination: Path,
    max_bytes: int,
    timeout_seconds: int,
    max_redirects: int = 1,
) -> GitHubArchiveMetadata:
    """Download a bounded archive from fixed GitHub hosts into ``destination``.

    Repository metadata and commit resolution are requested from the GitHub REST
    API. The archive endpoint is allowed to redirect exactly once to the fixed
    codeload host; all bytes are first written to a sibling temporary file and
    atomically moved only after the byte cap has been enforced.
    """
    repository = parse_public_github_url(repository_url)
    _validate_download_limits(max_bytes, timeout_seconds, max_redirects)
    target_path = Path(destination)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.trust_env = False
    session.verify = True
    try:
        repository_metadata = _fetch_json(
            session,
            f"{_GITHUB_API_BASE_URL}/repos/{repository.owner}/{repository.repository}",
            timeout_seconds,
        )
        default_branch = _read_public_repository_default_branch(repository_metadata)
        commit_sha = _fetch_commit_sha(session, repository, default_branch, timeout_seconds)
        archive_url = f"{_GITHUB_API_BASE_URL}/repos/{repository.owner}/{repository.repository}/zipball/{commit_sha}"
        redirect_response = _get(session, archive_url, timeout_seconds, stream=False)
        try:
            codeload_url = _read_codeload_redirect(redirect_response, repository, commit_sha)
        finally:
            redirect_response.close()

        archive_response = _get(session, codeload_url, timeout_seconds, stream=True)
        try:
            archive_bytes = _write_bounded_archive(archive_response, target_path, max_bytes)
        finally:
            archive_response.close()
    except GitHubSourceError:
        raise
    except requests.RequestException as exc:
        raise GitHubSourceError("GitHub 归档下载失败") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise GitHubSourceError("GitHub 归档下载失败") from exc
    finally:
        session.close()

    return GitHubArchiveMetadata(
        repository=repository,
        source_ref=default_branch,
        default_branch=default_branch,
        commit_sha=commit_sha,
        archive_path=target_path,
        archive_bytes=archive_bytes,
    )


def _validate_download_limits(max_bytes: int, timeout_seconds: int, max_redirects: int) -> None:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise GitHubSourceError("归档大小限制无效")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        raise GitHubSourceError("下载超时配置无效")
    if isinstance(max_redirects, bool) or not isinstance(max_redirects, int) or max_redirects != 1:
        raise GitHubSourceError("GitHub 重定向限制必须为 1")


def _get(session: requests.Session, url: str, timeout_seconds: int, *, stream: bool) -> requests.Response:
    return session.get(
        url,
        timeout=timeout_seconds,
        allow_redirects=False,
        stream=stream,
        headers={"Accept": "application/vnd.github+json"},
    )


def _fetch_json(session: requests.Session, url: str, timeout_seconds: int) -> dict[str, Any]:
    response = _get(session, url, timeout_seconds, stream=False)
    try:
        if response.status_code != 200:
            raise GitHubSourceError("GitHub 仓库元数据不可用")
        payload = response.json()
    finally:
        response.close()

    if not isinstance(payload, dict):
        raise GitHubSourceError("GitHub 仓库元数据无效")
    return payload


def _read_public_repository_default_branch(metadata: dict[str, Any]) -> str:
    if metadata.get("private") or metadata.get("disabled") or metadata.get("archived"):
        raise GitHubSourceError("GitHub 仓库不可用于扫描")

    default_branch = metadata.get("default_branch")
    if not isinstance(default_branch, str) or not default_branch or len(default_branch) > 255:
        raise GitHubSourceError("GitHub 仓库元数据无效")
    return default_branch


def _fetch_commit_sha(
    session: requests.Session,
    repository: GitHubRepositoryRef,
    default_branch: str,
    timeout_seconds: int,
) -> str:
    response = _get(
        session,
        f"{_GITHUB_API_BASE_URL}/repos/{repository.owner}/{repository.repository}/commits/{default_branch}",
        timeout_seconds,
        stream=False,
    )
    try:
        if response.status_code != 200:
            raise GitHubSourceError("GitHub 提交信息不可用")
        payload = response.json()
    finally:
        response.close()

    commit_sha = payload.get("sha") if isinstance(payload, dict) else None
    if not isinstance(commit_sha, str) or not _COMMIT_SHA_PATTERN.fullmatch(commit_sha):
        raise GitHubSourceError("GitHub 提交信息无效")
    return commit_sha.lower()


def _read_codeload_redirect(
    response: requests.Response,
    repository: GitHubRepositoryRef,
    commit_sha: str,
) -> str:
    if response.status_code not in {301, 302, 303, 307, 308}:
        raise GitHubSourceError("GitHub 归档重定向无效")

    location = response.headers.get("Location")
    if not isinstance(location, str) or not location:
        raise GitHubSourceError("GitHub 归档重定向无效")

    try:
        parsed = urlsplit(location)
        port = parsed.port
    except ValueError as exc:
        raise GitHubSourceError("GitHub 归档重定向无效") from exc

    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != _GITHUB_CODELOAD_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise GitHubSourceError("GitHub 归档重定向无效")

    expected_paths = {
        f"/{repository.owner}/{repository.repository}/zip/{commit_sha}",
        f"/{repository.owner}/{repository.repository}/legacy.zip/{commit_sha}",
    }
    if parsed.path not in expected_paths:
        raise GitHubSourceError("GitHub 归档重定向无效")
    return location


def _write_bounded_archive(response: requests.Response, destination: Path, max_bytes: int) -> int:
    if response.status_code != 200:
        raise GitHubSourceError("GitHub 归档下载失败")

    declared_length = response.headers.get("Content-Length")
    if declared_length is not None:
        try:
            content_length = int(declared_length)
        except (TypeError, ValueError) as exc:
            raise GitHubSourceError("GitHub 归档响应无效") from exc
        if content_length < 0 or content_length > max_bytes:
            raise GitHubSourceError("GitHub 归档超过大小限制")

    temporary_path: Path | None = None
    total_bytes = 0
    try:
        with tempfile.NamedTemporaryFile(
            mode="xb",
            prefix=f".{destination.name}.",
            suffix=".part",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise GitHubSourceError("GitHub 归档超过大小限制")
                temporary_file.write(chunk)
        os.replace(temporary_path, destination)
        temporary_path = None
        return total_bytes
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
