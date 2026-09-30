"""Tests for PrUpdaterService (ITQ-28 / #427).

Covers:
- In-Range bump (lockfile updated, manifest untouched, PR opened).
- Out-of-Range bump (manifest updated, lockfile updated, PR opened).
- Supersede/refresh (existing open PR updated, duplicate PR avoided).
- Edge cases: not opted in, feature flag disabled, asset not pinned, already up to date, prereleases ignored.
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock

import httpx
import pytest

from apps.content.models import Asset, AssetVersion, CategoryChoice, VersionStateChoice
from apps.dependabot.models import WatchedRepository
from apps.dependabot.services.github_client import (
    LOCKFILE_PATH,
    MANIFEST_PATH,
    GitHubContentsClient,
)
from apps.dependabot.services.github_token import GitHubInstallationTokenService
from apps.dependabot.services.manifest_discovery import ManifestDiscoveryService
from apps.dependabot.services.pr_updater import PrUpdaterService


def _make_updater(client: GitHubContentsClient | None = None) -> PrUpdaterService:
    c = client or MagicMock()
    watched_service = MagicMock()
    discovery_service = ManifestDiscoveryService(contents_client=c, watched_service=watched_service)
    return PrUpdaterService(github_client=c, discovery_service=discovery_service)


OWNER = "itqan-community"
REPO = "sample-app"
INSTALLATION_ID = 12345
SLUG = "quran-uthmani-hafs"

SAMPLE_MANIFEST = f"""schema_version: 1

assets:
  {SLUG}:
    version: "^1.2.0"
"""

SAMPLE_LOCKFILE = f"""lockfile_version: 1
manifest_schema_version: 1

assets:
  "{SLUG}":
    constraint: "^1.2.0"
    version: "1.2.3"
"""


class StubTokenService(GitHubInstallationTokenService):
    def get_installation_token(self, installation_id: int) -> str:
        return "ghs_test_token"


def _make_asset_and_version(
    *,
    slug: str = SLUG,
    name: str = "1.3.0",
    summary: str = "Fixed verse 5 text",
    state: str = VersionStateChoice.PUBLISHED,
) -> AssetVersion:
    asset = MagicMock(spec=Asset)
    asset.slug = slug
    asset.name = "Quran Uthmani Hafs"
    asset.category = CategoryChoice.MUSHAF

    version = MagicMock(spec=AssetVersion)
    version.asset = asset
    version.name = name
    version.summary = summary
    version.state = state
    return version


def _make_watched_repo(*, status: str = WatchedRepository.StatusChoice.OPTED_IN) -> WatchedRepository:
    repo = MagicMock(spec=WatchedRepository)
    repo.host = "github"
    repo.owner = OWNER
    repo.repository_name = REPO
    repo.installation_id = INSTALLATION_ID
    repo.status = status
    repo.is_opted_in = status == WatchedRepository.StatusChoice.OPTED_IN
    return repo


@pytest.fixture(autouse=True)
def enable_dependabot(settings):
    settings.ENABLE_ITQAN_DEPENDABOT = True
    settings.GITHUB_APP_ID = 1
    settings.GITHUB_APP_PRIVATE_KEY = "fake-pem"
    settings.GITHUB_API_BASE_URL = "https://api.github.com"
    settings.GITHUB_HTTP_TIMEOUT_SECONDS = 5.0
    settings.GITHUB_TOKEN_CACHE_SKEW_SECONDS = 60
    settings.GITHUB_WEBHOOK_SECRET = "secret"


def test_in_range_bump_updates_lockfile_only_and_opens_pr():
    created_pr = {}
    committed_files = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        # 1. Metadata
        if url == f"https://api.github.com/repos/{OWNER}/{REPO}":
            return httpx.Response(200, json={"default_branch": "main"})
        # 2. Get manifest
        if f"/contents/{MANIFEST_PATH}" in url:
            encoded = base64.b64encode(SAMPLE_MANIFEST.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": MANIFEST_PATH,
                    "sha": "a" * 40,
                    "content": encoded,
                    "size": len(SAMPLE_MANIFEST),
                    "encoding": "base64",
                },
            )
        # 3. Get lockfile
        if f"/contents/{LOCKFILE_PATH}" in url:
            encoded = base64.b64encode(SAMPLE_LOCKFILE.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": LOCKFILE_PATH,
                    "sha": "b" * 40,
                    "content": encoded,
                    "size": len(SAMPLE_LOCKFILE),
                    "encoding": "base64",
                },
            )
        # 4. Git ref for main
        if url.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "base_commit_1"}})
        # 5. Git commit base_commit_1
        if url.endswith("/git/commits/base_commit_1"):
            return httpx.Response(200, json={"sha": "base_commit_1", "tree": {"sha": "base_tree_1"}})
        # 6. Create tree
        if url.endswith("/git/trees"):
            body = request.read().decode("utf-8")
            committed_files["body"] = body
            return httpx.Response(201, json={"sha": "new_tree_sha"})
        # 7. Create commit
        if url.endswith("/git/commits"):
            return httpx.Response(201, json={"sha": "new_commit_sha"})
        # 8. Create or update ref
        if url.endswith("/git/refs"):
            return httpx.Response(201, json={"ref": "refs/heads/itqan-dependabot/assets/quran-uthmani-hafs"})
        # 9. List open PRs
        if "/pulls" in url and request.method == "GET":
            return httpx.Response(200, json=[])
        # 10. Create PR
        if "/pulls" in url and request.method == "POST":
            import json

            payload = json.loads(request.read())
            created_pr.update(payload)
            return httpx.Response(
                201,
                json={
                    "number": 101,
                    "title": payload["title"],
                    "body": payload["body"],
                    "head": {"ref": payload["head"]},
                    "base": {"ref": payload["base"]},
                    "state": "open",
                    "html_url": "https://github.com/itqan-community/sample-app/pull/101",
                },
            )
        return httpx.Response(404, json={"message": f"Unhandled {request.method} {url}"})

    client = GitHubContentsClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        token_service=StubTokenService(),
    )
    updater = _make_updater(client)
    watched = _make_watched_repo()
    version = _make_asset_and_version(name="1.3.0")

    result = updater.process_repository(watched, version)

    assert result.action == "created"
    assert result.is_in_range is True
    assert result.old_version == "1.2.3"
    assert result.new_version == "1.3.0"
    assert result.pr is not None
    assert result.pr.number == 101
    assert "update quran-uthmani-hafs to 1.3.0" in result.pr.title

    # Lockfile only was updated in git tree
    assert "itqan-assets.lock" in committed_files["body"]
    assert "itqan-assets.yaml" not in committed_files["body"]


def test_out_of_range_bump_updates_both_and_opens_pr():
    out_of_range_manifest = f"""schema_version: 1

assets:
  {SLUG}:
    version: "~1.2.0"
"""
    out_of_range_lockfile = f"""lockfile_version: 1
manifest_schema_version: 1

assets:
  "{SLUG}":
    constraint: "~1.2.0"
    version: "1.2.5"
"""
    created_pr = {}
    committed_files = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == f"https://api.github.com/repos/{OWNER}/{REPO}":
            return httpx.Response(200, json={"default_branch": "main"})
        if f"/contents/{MANIFEST_PATH}" in url:
            encoded = base64.b64encode(out_of_range_manifest.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": MANIFEST_PATH,
                    "sha": "a" * 40,
                    "content": encoded,
                    "size": len(out_of_range_manifest),
                    "encoding": "base64",
                },
            )
        if f"/contents/{LOCKFILE_PATH}" in url:
            encoded = base64.b64encode(out_of_range_lockfile.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": LOCKFILE_PATH,
                    "sha": "b" * 40,
                    "content": encoded,
                    "size": len(out_of_range_lockfile),
                    "encoding": "base64",
                },
            )
        if url.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "base_commit_1"}})
        if url.endswith("/git/commits/base_commit_1"):
            return httpx.Response(200, json={"sha": "base_commit_1", "tree": {"sha": "base_tree_1"}})
        if url.endswith("/git/trees"):
            body = request.read().decode("utf-8")
            committed_files["body"] = body
            return httpx.Response(201, json={"sha": "new_tree_sha"})
        if url.endswith("/git/commits"):
            return httpx.Response(201, json={"sha": "new_commit_sha"})
        if url.endswith("/git/refs"):
            return httpx.Response(201, json={"ref": "refs/heads/itqan-dependabot/assets/quran-uthmani-hafs"})
        if "/pulls" in url and request.method == "GET":
            return httpx.Response(200, json=[])
        if "/pulls" in url and request.method == "POST":
            import json

            payload = json.loads(request.read())
            created_pr.update(payload)
            return httpx.Response(
                201,
                json={
                    "number": 102,
                    "title": payload["title"],
                    "body": payload["body"],
                    "head": {"ref": payload["head"]},
                    "base": {"ref": payload["base"]},
                    "state": "open",
                    "html_url": "https://github.com/itqan-community/sample-app/pull/102",
                },
            )
        return httpx.Response(404, json={"message": f"Unhandled {request.method} {url}"})

    client = GitHubContentsClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        token_service=StubTokenService(),
    )
    updater = _make_updater(client)
    watched = _make_watched_repo()
    version = _make_asset_and_version(name="1.3.0")

    result = updater.process_repository(watched, version)

    assert result.action == "created"
    assert result.is_in_range is False
    assert result.old_version == "1.2.5"
    assert result.new_version == "1.3.0"
    assert result.pr is not None
    assert result.pr.number == 102
    assert "bump quran-uthmani-hafs from 1.2.5 to 1.3.0" in result.pr.title

    # Both manifest and lockfile were updated
    assert "itqan-assets.lock" in committed_files["body"]
    assert "itqan-assets.yaml" in committed_files["body"]


def test_supersedes_existing_pr_instead_of_stacking_duplicates():
    updated_pr = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == f"https://api.github.com/repos/{OWNER}/{REPO}":
            return httpx.Response(200, json={"default_branch": "main"})
        if f"/contents/{MANIFEST_PATH}" in url:
            encoded = base64.b64encode(SAMPLE_MANIFEST.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": MANIFEST_PATH,
                    "sha": "a" * 40,
                    "content": encoded,
                    "size": len(SAMPLE_MANIFEST),
                    "encoding": "base64",
                },
            )
        if f"/contents/{LOCKFILE_PATH}" in url:
            encoded = base64.b64encode(SAMPLE_LOCKFILE.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": LOCKFILE_PATH,
                    "sha": "b" * 40,
                    "content": encoded,
                    "size": len(SAMPLE_LOCKFILE),
                    "encoding": "base64",
                },
            )
        if url.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "base_commit_1"}})
        if url.endswith("/git/commits/base_commit_1"):
            return httpx.Response(200, json={"sha": "base_commit_1", "tree": {"sha": "base_tree_1"}})
        if url.endswith("/git/trees"):
            return httpx.Response(201, json={"sha": "new_tree_sha"})
        if url.endswith("/git/commits"):
            return httpx.Response(201, json={"sha": "new_commit_sha"})
        if url.endswith("/git/refs"):
            # Ref already exists, returns 422
            return httpx.Response(422, json={"message": "Reference already exists"})
        if "/git/refs/heads/itqan-dependabot/assets/quran-uthmani-hafs" in url and request.method == "PATCH":
            return httpx.Response(200, json={"ref": "refs/heads/itqan-dependabot/assets/quran-uthmani-hafs"})
        # List open PRs returns an existing PR #88!
        if "/pulls" in url and request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 88,
                        "title": "chore: old pr",
                        "body": "old body",
                        "head": {"ref": "itqan-dependabot/assets/quran-uthmani-hafs"},
                        "base": {"ref": "main"},
                        "state": "open",
                        "html_url": "https://github.com/itqan-community/sample-app/pull/88",
                    }
                ],
            )
        # Update PR #88
        if url.endswith("/pulls/88") and request.method == "PATCH":
            import json

            payload = json.loads(request.read())
            updated_pr.update(payload)
            return httpx.Response(
                200,
                json={
                    "number": 88,
                    "title": payload["title"],
                    "body": payload["body"],
                    "head": {"ref": "itqan-dependabot/assets/quran-uthmani-hafs"},
                    "base": {"ref": "main"},
                    "state": "open",
                    "html_url": "https://github.com/itqan-community/sample-app/pull/88",
                },
            )
        return httpx.Response(404, json={"message": f"Unhandled {request.method} {url}"})

    client = GitHubContentsClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        token_service=StubTokenService(),
    )
    updater = _make_updater(client)
    watched = _make_watched_repo()
    version = _make_asset_and_version(name="1.3.0")

    result = updater.process_repository(watched, version)

    assert result.action == "superseded"
    assert result.pr is not None
    assert result.pr.number == 88
    assert "update quran-uthmani-hafs to 1.3.0" in updated_pr["title"]
    assert "Bumps `quran-uthmani-hafs` from `1.2.3` to `1.3.0`" in updated_pr["body"]


def test_skips_when_repository_not_opted_in():
    updater = _make_updater()
    watched = _make_watched_repo(status=WatchedRepository.StatusChoice.OPTED_OUT)
    version = _make_asset_and_version(name="1.3.0")

    result = updater.process_repository(watched, version)
    assert result.action == "skipped"
    assert result.reason == "not_opted_in"


def test_skips_when_dependabot_disabled(settings):
    settings.ENABLE_ITQAN_DEPENDABOT = False
    updater = _make_updater()
    watched = _make_watched_repo()
    version = _make_asset_and_version(name="1.3.0")

    result = updater.process_repository(watched, version)
    assert result.action == "skipped"
    assert result.reason == "dependabot_disabled"


def test_skips_when_asset_not_pinned():
    manifest_without_asset = """schema_version: 1

assets:
  other-asset:
    version: "^1.0.0"
"""
    lockfile_without_asset = """lockfile_version: 1
manifest_schema_version: 1

assets:
  "other-asset":
    constraint: "^1.0.0"
    version: "1.0.0"
"""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == f"https://api.github.com/repos/{OWNER}/{REPO}":
            return httpx.Response(200, json={"default_branch": "main"})
        if f"/contents/{MANIFEST_PATH}" in url:
            encoded = base64.b64encode(manifest_without_asset.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": MANIFEST_PATH,
                    "sha": "a" * 40,
                    "content": encoded,
                    "size": len(manifest_without_asset),
                    "encoding": "base64",
                },
            )
        if f"/contents/{LOCKFILE_PATH}" in url:
            encoded = base64.b64encode(lockfile_without_asset.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": LOCKFILE_PATH,
                    "sha": "b" * 40,
                    "content": encoded,
                    "size": len(lockfile_without_asset),
                    "encoding": "base64",
                },
            )
        return httpx.Response(404)

    client = GitHubContentsClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        token_service=StubTokenService(),
    )
    updater = _make_updater(client)
    watched = _make_watched_repo()
    version = _make_asset_and_version(slug="quran-uthmani-hafs", name="1.3.0")

    result = updater.process_repository(watched, version)
    assert result.action == "skipped"
    assert result.reason == "asset_not_pinned"


def test_skips_when_already_up_to_date():
    lockfile_up_to_date = f"""lockfile_version: 1
manifest_schema_version: 1

assets:
  "{SLUG}":
    constraint: "^1.2.0"
    version: "1.3.0"
"""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == f"https://api.github.com/repos/{OWNER}/{REPO}":
            return httpx.Response(200, json={"default_branch": "main"})
        if f"/contents/{MANIFEST_PATH}" in url:
            encoded = base64.b64encode(SAMPLE_MANIFEST.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": MANIFEST_PATH,
                    "sha": "a" * 40,
                    "content": encoded,
                    "size": len(SAMPLE_MANIFEST),
                    "encoding": "base64",
                },
            )
        if f"/contents/{LOCKFILE_PATH}" in url:
            encoded = base64.b64encode(lockfile_up_to_date.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": LOCKFILE_PATH,
                    "sha": "b" * 40,
                    "content": encoded,
                    "size": len(lockfile_up_to_date),
                    "encoding": "base64",
                },
            )
        return httpx.Response(404)

    client = GitHubContentsClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        token_service=StubTokenService(),
    )
    updater = _make_updater(client)
    watched = _make_watched_repo()
    version = _make_asset_and_version(name="1.3.0")

    result = updater.process_repository(watched, version)
    assert result.action == "skipped"
    assert result.reason == "already_up_to_date"


def test_skips_prerelease_on_ranged_constraint():
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == f"https://api.github.com/repos/{OWNER}/{REPO}":
            return httpx.Response(200, json={"default_branch": "main"})
        if f"/contents/{MANIFEST_PATH}" in url:
            encoded = base64.b64encode(SAMPLE_MANIFEST.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": MANIFEST_PATH,
                    "sha": "a" * 40,
                    "content": encoded,
                    "size": len(SAMPLE_MANIFEST),
                    "encoding": "base64",
                },
            )
        if f"/contents/{LOCKFILE_PATH}" in url:
            encoded = base64.b64encode(SAMPLE_LOCKFILE.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": LOCKFILE_PATH,
                    "sha": "b" * 40,
                    "content": encoded,
                    "size": len(SAMPLE_LOCKFILE),
                    "encoding": "base64",
                },
            )
        return httpx.Response(404)

    client = GitHubContentsClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        token_service=StubTokenService(),
    )
    updater = _make_updater(client)
    watched = _make_watched_repo()
    # New version is a prerelease: 1.4.0-alpha.1, while constraint is ^1.2.0
    version = _make_asset_and_version(name="1.4.0-alpha.1")

    result = updater.process_repository(watched, version)
    assert result.action == "skipped"
    assert result.reason == "prerelease_ignored_by_range"


def test_process_repository_skips_when_newer_pr_already_open():
    commit_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/git/commits" in url:
            commit_calls.append(request)
        if url.endswith(f"/repos/{OWNER}/{REPO}"):
            return httpx.Response(200, json={"default_branch": "main"})
        if f"/contents/{MANIFEST_PATH}" in url:
            encoded = base64.b64encode(SAMPLE_MANIFEST.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": MANIFEST_PATH,
                    "sha": "a" * 40,
                    "content": encoded,
                    "size": len(SAMPLE_MANIFEST),
                    "encoding": "base64",
                },
            )
        if f"/contents/{LOCKFILE_PATH}" in url:
            encoded = base64.b64encode(SAMPLE_LOCKFILE.encode("utf-8")).decode("ascii")
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "path": LOCKFILE_PATH,
                    "sha": "b" * 40,
                    "content": encoded,
                    "size": len(SAMPLE_LOCKFILE),
                    "encoding": "base64",
                },
            )
        if "/pulls" in url and request.method == "GET":
            # Existing open PR already bumped to 1.4.0
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 99,
                        "title": "chore(deps): bump quran-uthmani-hafs to 1.4.0",
                        "body": "Existing PR",
                        "head": {"ref": "itqan-dependabot/assets/quran-uthmani-hafs"},
                        "base": {"ref": "main"},
                        "state": "open",
                        "html_url": "https://github.com/itqan-community/sample-app/pull/99",
                    }
                ],
            )
        return httpx.Response(404)

    client = GitHubContentsClient(
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        token_service=StubTokenService(),
    )
    updater = _make_updater(client)
    watched = _make_watched_repo()
    # Attempting to process older version 1.3.0
    version = _make_asset_and_version(name="1.3.0")

    result = updater.process_repository(watched, version)
    assert result.action == "skipped"
    assert result.reason == "older_or_equal_to_open_pr"
    assert result.pr.number == 99
    # Ensure commit_files was NOT called
    assert len(commit_calls) == 0
