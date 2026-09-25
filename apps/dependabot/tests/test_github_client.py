"""Tests for the read-only GitHub contents client.

HTTP is fully mocked with ``httpx.MockTransport``: zero live GitHub calls.
A stub token service (subclassing the real one, so types stay honest)
removes settings/crypto from every test except the Authorization assertions.
"""

from __future__ import annotations

import base64
import logging

from django.test import SimpleTestCase
import httpx
import pytest

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.services.github_client import (
    ALLOWED_MANIFEST_PATHS,
    MANIFEST_PATH,
    MAX_DECODED_BYTES,
    DiscoveredFile,
    GitHubContentsClient,
)
from apps.dependabot.services.github_token import GitHubInstallationTokenService

OWNER = "itqan-community"
REPO = "sample-app"
INSTALLATION_ID = 424242
STUB_TOKEN = "ghs_stub_installation_token"
FILE_SHA = "c" * 40


class StubTokenService(GitHubInstallationTokenService):
    """Token service stub: no settings, no crypto, fixed token."""

    def __init__(self, token: str = STUB_TOKEN) -> None:
        super().__init__()
        self._stub_token = token

    def get_installation_token(self, installation_id: int) -> str:
        return self._stub_token


def _client(handler, **kwargs) -> GitHubContentsClient:
    kwargs.setdefault("token_service", StubTokenService())
    return GitHubContentsClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        **kwargs,
    )


def _file_body(text: str, *, sha: str = FILE_SHA, path: str = MANIFEST_PATH) -> dict:
    return {
        "type": "file",
        "encoding": "base64",
        "size": len(text.encode("utf-8")),
        "name": path,
        "path": path,
        "sha": sha,
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }


# --- Repository metadata ---


def test_metadata_where_valid_returns_default_branch():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json={"default_branch": "develop", "full_name": f"{OWNER}/{REPO}"})

    metadata = _client(handler).get_repository(owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID)

    assert metadata.default_branch == "develop"
    assert seen["method"] == "GET"
    assert seen["url"] == f"https://api.github.com/repos/{OWNER}/{REPO}"
    assert seen["headers"]["authorization"] == f"Bearer {STUB_TOKEN}"
    assert seen["headers"]["accept"] == "application/vnd.github+json"
    assert seen["headers"]["x-github-api-version"] == "2022-11-28"
    assert seen["headers"]["user-agent"] == "itqan-dependabot"


@pytest.mark.parametrize(
    "status, body, name, code",
    [
        (404, {"message": "Not Found"}, "github_repository_unavailable", 404),
        (401, {"message": "Bad credentials"}, "github_authentication_failed", 401),
        (403, {"message": "Resource not accessible by integration"}, "github_access_denied", 403),
        (500, {"message": "Internal Server Error"}, "github_upstream_error", 502),
    ],
)
def test_metadata_where_error_status_mapped(status, body, name, code):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    with pytest.raises(ItqanError) as exc_info:
        _client(handler).get_repository(owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID)
    assert exc_info.value.error_name == name
    assert exc_info.value.status_code == code


def test_metadata_where_rate_limited_mapped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "30"}, json={"message": "API rate limit exceeded"})

    with pytest.raises(ItqanError) as exc_info:
        _client(handler).get_repository(owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID)
    assert exc_info.value.error_name == "github_rate_limited"
    assert exc_info.value.extra == {"retry_after_seconds": 30}


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        ["a", "list"],
        {"full_name": "x/y"},
        {"default_branch": ""},
        {"default_branch": 123},
    ],
)
def test_metadata_where_malformed_mapped(body):
    if isinstance(body, bytes):
        response = httpx.Response(200, content=body)
    else:
        response = httpx.Response(200, json=body)

    def handler(request: httpx.Request) -> httpx.Response:
        return response

    with pytest.raises(ItqanError) as exc_info:
        _client(handler).get_repository(owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID)
    assert exc_info.value.error_name == "github_malformed_response"


@pytest.mark.parametrize("exc", [httpx.ConnectTimeout("timed out"), httpx.ConnectError("refused")])
def test_metadata_where_transport_fails_mapped_to_upstream_error(exc):
    def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    with pytest.raises(ItqanError) as exc_info:
        _client(handler).get_repository(owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID)
    assert exc_info.value.error_name == "github_upstream_error"


# --- File fetching ---


def test_file_where_present_returns_decoded_content():
    seen: dict = {}
    text = "schema_version: 1\nassets: {}\n"

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json=_file_body(text))

    result = _client(handler).get_file(
        owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID, path=MANIFEST_PATH, ref="develop"
    )

    assert result == DiscoveredFile(path=MANIFEST_PATH, present=True, sha=FILE_SHA, content=text.encode())
    assert seen["url"] == f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{MANIFEST_PATH}?ref=develop"
    assert seen["headers"]["authorization"] == f"Bearer {STUB_TOKEN}"


def test_file_where_404_is_absence_not_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    result = _client(handler).get_file(
        owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID, path=MANIFEST_PATH, ref="main"
    )
    assert result == DiscoveredFile(path=MANIFEST_PATH, present=False, sha=None, content=None)


@pytest.mark.parametrize("path", list(ALLOWED_MANIFEST_PATHS))
def test_file_where_both_v1_paths_allowed(path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    assert (
        _client(handler)
        .get_file(owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID, path=path, ref="main")
        .present
        is False
    )


def test_file_where_other_path_rejected_without_request():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        calls.append(request)
        return httpx.Response(200, json={})

    with pytest.raises(ItqanError) as exc_info:
        _client(handler).get_file(
            owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID, path="package.json", ref="main"
        )
    assert exc_info.value.error_name == "github_unsupported_manifest_path"
    assert calls == []


@pytest.mark.parametrize(
    "payload",
    [
        [{"type": "file", "path": MANIFEST_PATH}],
        {"type": "dir", "path": MANIFEST_PATH},
        {"type": "submodule", "path": MANIFEST_PATH, "sha": FILE_SHA},
        {"type": "symlink", "path": MANIFEST_PATH, "sha": FILE_SHA},
        {"type": "file", "path": "other.yaml", "sha": FILE_SHA, "encoding": "base64", "content": "eA=="},
        {"type": "file", "path": MANIFEST_PATH, "sha": "not-a-sha", "encoding": "base64", "content": "eA=="},
        {"type": "file", "path": MANIFEST_PATH, "sha": FILE_SHA, "encoding": "utf-8", "content": "eA=="},
        {"type": "file", "path": MANIFEST_PATH, "sha": FILE_SHA, "encoding": "base64", "content": "!!!"},
        {
            "type": "file",
            "path": MANIFEST_PATH,
            "sha": FILE_SHA,
            "encoding": "base64",
            "size": MAX_DECODED_BYTES + 1,
            "content": "eA==",
        },
        "just a string",
        42,
    ],
    ids=[
        "directory-listing",
        "wrong-type-dir",
        "wrong-type-submodule",
        "wrong-type-symlink",
        "path-mismatch",
        "invalid-sha",
        "wrong-encoding",
        "invalid-base64",
        "oversized",
        "scalar-body",
        "int-body",
    ],
)
def test_file_where_undecodable_is_present_but_unreadable(payload):
    if isinstance(payload, str | int):
        response = httpx.Response(200, json=payload)
    else:
        response = httpx.Response(200, json=payload)

    def handler(request: httpx.Request) -> httpx.Response:
        return response

    result = _client(handler).get_file(
        owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID, path=MANIFEST_PATH, ref="main"
    )
    assert result.present is True
    assert result.sha is None
    assert result.content is None


def test_file_where_empty_file_decodes_to_empty_bytes():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"type": "file", "path": MANIFEST_PATH, "sha": FILE_SHA, "size": 0, "content": ""},
        )

    result = _client(handler).get_file(
        owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID, path=MANIFEST_PATH, ref="main"
    )
    assert result == DiscoveredFile(path=MANIFEST_PATH, present=True, sha=FILE_SHA, content=b"")


@pytest.mark.parametrize(
    "status, name",
    [(401, "github_authentication_failed"), (403, "github_access_denied"), (500, "github_upstream_error")],
)
def test_file_where_error_status_mapped(status, name):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "nope"})

    with pytest.raises(ItqanError) as exc_info:
        _client(handler).get_file(
            owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID, path=MANIFEST_PATH, ref="main"
        )
    assert exc_info.value.error_name == name


# --- Secrecy ---


class GitHubClientSecrecyTest(SimpleTestCase):
    def test_client_does_not_log_authorization_header(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"message": "boom"})

        with self.assertLogs("apps.dependabot.services.github_client", level=logging.DEBUG) as cm:
            with self.assertRaises(ItqanError) as ctx:
                _client(handler).get_repository(owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID)
        assert ctx.exception.error_name == "github_upstream_error"
        assert STUB_TOKEN not in ctx.exception.message
        assert STUB_TOKEN not in str(ctx.exception.extra)
        for record in cm.records:
            assert STUB_TOKEN not in record.getMessage()
            assert "Bearer " not in record.getMessage()


# --- Git References, Commits, and Pull Requests ---


def test_get_ref_returns_commit_sha():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"https://api.github.com/repos/{OWNER}/{REPO}/git/ref/heads/main"
        assert request.method == "GET"
        return httpx.Response(200, json={"object": {"sha": "commit_sha_123", "type": "commit"}})

    client = _client(handler)
    sha = client.get_ref(owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID, ref="heads/main")
    assert sha == "commit_sha_123"


def test_get_commit_returns_tree_sha():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"https://api.github.com/repos/{OWNER}/{REPO}/git/commits/commit_123"
        return httpx.Response(200, json={"sha": "commit_123", "tree": {"sha": "tree_abc"}})

    client = _client(handler)
    commit = client.get_commit(
        owner=OWNER, repository_name=REPO, installation_id=INSTALLATION_ID, commit_sha="commit_123"
    )
    assert commit["tree"]["sha"] == "tree_abc"


def test_create_tree_returns_new_tree_sha():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"https://api.github.com/repos/{OWNER}/{REPO}/git/trees"
        assert request.method == "POST"
        body = request.read().decode("utf-8")
        assert "itqan-assets.lock" in body
        return httpx.Response(201, json={"sha": "new_tree_456"})

    client = _client(handler)
    tree_sha = client.create_tree(
        owner=OWNER,
        repository_name=REPO,
        installation_id=INSTALLATION_ID,
        base_tree="base_tree_123",
        tree=[{"path": "itqan-assets.lock", "mode": "100644", "type": "blob", "content": "hello"}],
    )
    assert tree_sha == "new_tree_456"


def test_create_commit_returns_new_commit_sha():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"https://api.github.com/repos/{OWNER}/{REPO}/git/commits"
        assert request.method == "POST"
        return httpx.Response(201, json={"sha": "new_commit_789"})

    client = _client(handler)
    commit_sha = client.create_commit(
        owner=OWNER,
        repository_name=REPO,
        installation_id=INSTALLATION_ID,
        message="chore(deps): bump asset",
        tree="tree_456",
        parents=["parent_123"],
    )
    assert commit_sha == "new_commit_789"


def test_create_or_update_ref_creates_when_not_exists():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        return httpx.Response(201, json={"ref": "refs/heads/feature"})

    client = _client(handler)
    client.create_or_update_ref(
        owner=OWNER,
        repository_name=REPO,
        installation_id=INSTALLATION_ID,
        ref="heads/feature",
        sha="sha_123",
    )
    assert len(calls) == 1
    assert calls[0] == ("POST", f"https://api.github.com/repos/{OWNER}/{REPO}/git/refs")


def test_create_or_update_ref_updates_when_already_exists():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if request.method == "POST":
            return httpx.Response(422, json={"message": "Reference already exists"})
        return httpx.Response(200, json={"ref": "refs/heads/feature"})

    client = _client(handler)
    client.create_or_update_ref(
        owner=OWNER,
        repository_name=REPO,
        installation_id=INSTALLATION_ID,
        ref="heads/feature",
        sha="sha_123",
    )
    assert len(calls) == 2
    assert calls[0] == ("POST", f"https://api.github.com/repos/{OWNER}/{REPO}/git/refs")
    assert calls[1] == ("PATCH", f"https://api.github.com/repos/{OWNER}/{REPO}/git/refs/heads/feature")


def test_commit_files_orchestrates_entire_flow():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "base_commit"}})
        if request.url.path.endswith("/git/commits/base_commit"):
            return httpx.Response(200, json={"sha": "base_commit", "tree": {"sha": "base_tree"}})
        if request.url.path.endswith("/git/trees"):
            return httpx.Response(201, json={"sha": "new_tree"})
        if request.url.path.endswith("/git/commits"):
            return httpx.Response(201, json={"sha": "new_commit"})
        if request.url.path.endswith("/git/refs"):
            return httpx.Response(201, json={"ref": "refs/heads/bump-branch"})
        return httpx.Response(404)

    client = _client(handler)
    commit_sha = client.commit_files(
        owner=OWNER,
        repository_name=REPO,
        installation_id=INSTALLATION_ID,
        branch="bump-branch",
        base_branch="main",
        message="chore: update",
        files={"itqan-assets.lock": b"test content"},
    )
    assert commit_sha == "new_commit"
    assert len(requests) == 5


def test_list_pull_requests_parses_summaries():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "state=open" in str(request.url)
        assert f"head={OWNER}%3Abump-branch" in str(request.url) or f"head={OWNER}:bump-branch" in str(request.url)
        return httpx.Response(
            200,
            json=[
                {
                    "number": 42,
                    "title": "chore: bump asset",
                    "body": "PR description",
                    "head": {"ref": "bump-branch"},
                    "base": {"ref": "main"},
                    "state": "open",
                    "html_url": "https://github.com/itqan-community/sample-app/pull/42",
                }
            ],
        )

    client = _client(handler)
    prs = client.list_pull_requests(
        owner=OWNER,
        repository_name=REPO,
        installation_id=INSTALLATION_ID,
        head="bump-branch",
        state="open",
    )
    assert len(prs) == 1
    assert prs[0].number == 42
    assert prs[0].title == "chore: bump asset"
    assert prs[0].head_ref == "bump-branch"
    assert prs[0].base_ref == "main"


def test_create_pull_request_returns_summary():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url).endswith("/pulls")
        return httpx.Response(
            201,
            json={
                "number": 43,
                "title": "chore: new pr",
                "body": "body",
                "head": {"ref": "bump-branch"},
                "base": {"ref": "main"},
                "state": "open",
                "html_url": "https://github.com/itqan-community/sample-app/pull/43",
            },
        )

    client = _client(handler)
    pr = client.create_pull_request(
        owner=OWNER,
        repository_name=REPO,
        installation_id=INSTALLATION_ID,
        title="chore: new pr",
        body="body",
        head="bump-branch",
        base="main",
    )
    assert pr.number == 43
    assert pr.title == "chore: new pr"


def test_update_pull_request_returns_summary():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert str(request.url).endswith("/pulls/43")
        return httpx.Response(
            200,
            json={
                "number": 43,
                "title": "chore: updated title",
                "body": "updated body",
                "head": {"ref": "bump-branch"},
                "base": {"ref": "main"},
                "state": "open",
                "html_url": "https://github.com/itqan-community/sample-app/pull/43",
            },
        )

    client = _client(handler)
    pr = client.update_pull_request(
        owner=OWNER,
        repository_name=REPO,
        installation_id=INSTALLATION_ID,
        pull_number=43,
        title="chore: updated title",
        body="updated body",
    )
    assert pr.number == 43
    assert pr.title == "chore: updated title"
