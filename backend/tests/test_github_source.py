from pathlib import Path

import pytest

from app.services.github_source import (
    GitHubSourceError,
    download_public_github_archive,
    parse_public_github_url,
)


COMMIT_SHA = "a" * 40


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None, chunks=()):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self._chunks = tuple(chunks)
        self.closed = False

    def json(self):
        return self._payload

    def iter_content(self, chunk_size):
        del chunk_size
        yield from self._chunks

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.trust_env = True
        self.verify = False
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)

    def close(self):
        self.closed = True


def metadata_response(**overrides):
    payload = {
        "private": False,
        "disabled": False,
        "archived": False,
        "default_branch": "main",
    }
    payload.update(overrides)
    return FakeResponse(payload=payload)


def session_factory(monkeypatch, responses):
    session = FakeSession(responses)
    monkeypatch.setattr("app.services.github_source.requests.Session", lambda: session)
    return session


def successful_responses(archive_response):
    return [
        metadata_response(),
        FakeResponse(payload={"sha": COMMIT_SHA}),
        FakeResponse(
            status_code=302,
            headers={"Location": f"https://codeload.github.com/acme/demo/zip/{COMMIT_SHA}"},
        ),
        archive_response,
    ]


def test_parses_only_normalized_public_github_repository_urls():
    repository = parse_public_github_url("https://github.com/acme/demo/")

    assert repository.owner == "acme"
    assert repository.repository == "demo"
    assert repository.normalized_url == "https://github.com/acme/demo"
    assert repository.ref is None


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/acme/demo",
        "https://user@github.com/acme/demo",
        "https://github.com:443/acme/demo",
        "https://github.com/acme/demo?ref=main",
        "https://github.com/acme/demo#readme",
        "https://github.com/acme/demo/issues",
        "https://github.com/acme/demo.git",
        "git@github.com:acme/demo.git",
        "https://127.0.0.1/acme/demo",
        "https://github.com/acme/%2fdemo",
    ],
)
def test_rejects_non_normalized_or_non_public_github_urls(url):
    with pytest.raises(GitHubSourceError):
        parse_public_github_url(url)


@pytest.mark.parametrize(
    "repository_metadata",
    [
        {"private": True},
        {"disabled": True},
        {"archived": True},
    ],
)
def test_rejects_private_disabled_or_archived_repository_metadata(tmp_path, monkeypatch, repository_metadata):
    session = session_factory(monkeypatch, [metadata_response(**repository_metadata)])

    with pytest.raises(GitHubSourceError):
        download_public_github_archive(
            "https://github.com/acme/demo",
            tmp_path / "repo.zip",
            max_bytes=1024,
            timeout_seconds=5,
        )

    assert len(session.calls) == 1
    assert not (tmp_path / "repo.zip").exists()


def test_rejects_archive_redirect_outside_fixed_codeload_host(tmp_path, monkeypatch):
    session_factory(
        monkeypatch,
        [
            metadata_response(),
            FakeResponse(payload={"sha": COMMIT_SHA}),
            FakeResponse(status_code=302, headers={"Location": "https://evil.example/archive.zip"}),
        ],
    )

    with pytest.raises(GitHubSourceError):
        download_public_github_archive(
            "https://github.com/acme/demo",
            tmp_path / "repo.zip",
            max_bytes=1024,
            timeout_seconds=5,
        )

    assert not (tmp_path / "repo.zip").exists()


def test_rejects_archive_when_declared_content_length_exceeds_limit(tmp_path, monkeypatch):
    session_factory(
        monkeypatch,
        successful_responses(FakeResponse(headers={"Content-Length": "6"}, chunks=[b"123456"])),
    )

    with pytest.raises(GitHubSourceError):
        download_public_github_archive(
            "https://github.com/acme/demo",
            tmp_path / "repo.zip",
            max_bytes=5,
            timeout_seconds=5,
        )

    assert not (tmp_path / "repo.zip").exists()
    assert not list(tmp_path.glob(".repo.zip.*.part"))


def test_rejects_archive_when_streamed_content_exceeds_limit(tmp_path, monkeypatch):
    session_factory(
        monkeypatch,
        successful_responses(FakeResponse(chunks=[b"123", b"456"])),
    )

    with pytest.raises(GitHubSourceError):
        download_public_github_archive(
            "https://github.com/acme/demo",
            tmp_path / "repo.zip",
            max_bytes=5,
            timeout_seconds=5,
        )

    assert not (tmp_path / "repo.zip").exists()
    assert not list(tmp_path.glob(".repo.zip.*.part"))


def test_downloads_verified_archive_and_returns_reproducible_metadata(tmp_path, monkeypatch):
    session = session_factory(
        monkeypatch,
        successful_responses(FakeResponse(headers={"Content-Length": "4"}, chunks=[b"PK", b"\x03\x04"])),
    )
    destination = tmp_path / "repo.zip"

    result = download_public_github_archive(
        "https://github.com/acme/demo",
        destination,
        max_bytes=1024,
        timeout_seconds=5,
    )

    assert destination.read_bytes() == b"PK\x03\x04"
    assert result.source_ref == "main"
    assert result.default_branch == "main"
    assert result.commit_sha == COMMIT_SHA
    assert result.archive_path == destination
    assert result.archive_bytes == 4
    assert result.repository.normalized_url == "https://github.com/acme/demo"
    assert session.trust_env is False
    assert session.verify is True
    assert [call[0] for call in session.calls] == [
        "https://api.github.com/repos/acme/demo",
        "https://api.github.com/repos/acme/demo/commits/main",
        f"https://api.github.com/repos/acme/demo/zipball/{COMMIT_SHA}",
        f"https://codeload.github.com/acme/demo/zip/{COMMIT_SHA}",
    ]
    assert all(call[1]["timeout"] == 5 for call in session.calls)
    assert all(call[1]["allow_redirects"] is False for call in session.calls)
