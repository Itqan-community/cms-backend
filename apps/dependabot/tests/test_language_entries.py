"""Dependabot with language renditions: manifest entries may set `asset` and
`language`, and a newly published version only bumps the entry for its own
asset + language."""

from __future__ import annotations

import base64
import json

import httpx

from apps.dependabot.services.github_client import LOCKFILE_PATH, MANIFEST_PATH, DiscoveredFile, GitHubContentsClient
from apps.dependabot.services.manifest_parse import (
    FRESH,
    STALE,
    classify_discovery,
    parse_lockfile_document,
    parse_manifest_document,
)
from apps.dependabot.services.manifest_update import serialize_updated_lockfile
from apps.dependabot.tests.test_pr_updater import (
    OWNER,
    REPO,
    StubTokenService,
    _make_asset_and_version,
    _make_updater,
    _make_watched_repo,
)
from apps.dependabot.tests.test_pr_updater import enable_dependabot  # noqa: F401 - autouse fixture

MANIFEST = b"""schema_version: 1

assets:
  tafsir:
    version: "^1.0.0"
  tafsir-az:
    asset: tafsir
    language: az
    version: "^1.0.0"
"""

LOCKFILE = b"""lockfile_version: 1
manifest_schema_version: 1

assets:
  "tafsir":
    constraint: "^1.0.0"
    version: "1.4.0"
  "tafsir-az":
    asset: "tafsir"
    language: "az"
    constraint: "^1.0.0"
    version: "1.0.0"
"""


def _present(content: bytes, path: str = MANIFEST_PATH) -> DiscoveredFile:
    return DiscoveredFile(path=path, present=True, sha="a" * 40, content=content)


def _github_handler(captured: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == f"https://api.github.com/repos/{OWNER}/{REPO}":
            return httpx.Response(200, json={"default_branch": "main"})
        for path, content in ((MANIFEST_PATH, MANIFEST), (LOCKFILE_PATH, LOCKFILE)):
            if f"/contents/{path}" in url:
                return httpx.Response(
                    200,
                    json={
                        "type": "file",
                        "path": path,
                        "sha": "a" * 40,
                        "content": base64.b64encode(content).decode("ascii"),
                        "size": len(content),
                        "encoding": "base64",
                    },
                )
        if url.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "base"}})
        if url.endswith("/git/commits/base"):
            return httpx.Response(200, json={"sha": "base", "tree": {"sha": "tree"}})
        if url.endswith("/git/trees"):
            captured["tree"] = json.loads(request.read())
            return httpx.Response(201, json={"sha": "new_tree"})
        if url.endswith("/git/commits"):
            return httpx.Response(201, json={"sha": "new_commit"})
        if "/git/refs" in url:
            return httpx.Response(201, json={"ref": "refs/heads/branch"})
        if "/pulls" in url and request.method == "GET":
            return httpx.Response(200, json=[])
        if "/pulls" in url and request.method == "POST":
            payload = json.loads(request.read())
            captured["pr"] = payload
            return httpx.Response(
                201,
                json={
                    "number": 7,
                    "title": payload["title"],
                    "body": payload["body"],
                    "head": {"ref": payload["head"]},
                    "base": {"ref": payload["base"]},
                    "state": "open",
                    "html_url": f"https://github.com/{OWNER}/{REPO}/pull/7",
                },
            )
        return httpx.Response(404, json={"message": f"Unhandled {request.method} {url}"})

    return httpx.MockTransport(handler)


def test_parse_manifest_document_where_entry_sets_asset_and_language_should_keep_them():
    # Arrange / Act
    manifest = parse_manifest_document(MANIFEST)

    # Assert
    assert manifest.assets["tafsir-az"].asset == "tafsir"
    assert manifest.assets["tafsir-az"].language == "az"
    assert manifest.assets["tafsir"].asset is None
    assert manifest.assets["tafsir"].language is None


def test_classify_discovery_where_lockfile_matches_languages_should_be_fresh():
    # Arrange / Act
    result = classify_discovery(manifest=_present(MANIFEST), lockfile=_present(LOCKFILE, LOCKFILE_PATH))

    # Assert
    assert result.state == FRESH


def test_classify_discovery_where_manifest_language_differs_from_lockfile_should_be_stale():
    # Arrange
    manifest = MANIFEST.replace(b"language: az", b"language: tr")

    # Act
    result = classify_discovery(manifest=_present(manifest), lockfile=_present(LOCKFILE, LOCKFILE_PATH))

    # Assert
    assert result.state == STALE


def test_serialize_updated_lockfile_where_entry_has_language_should_keep_it():
    # Arrange
    lockfile = parse_lockfile_document(LOCKFILE)

    # Act
    updated = serialize_updated_lockfile(lockfile, slug="tafsir-az", new_constraint="^1.0.0", new_version="1.1.0")

    # Assert
    assert updated == LOCKFILE.replace(b'version: "1.0.0"', b'version: "1.1.0"')


def test_process_repository_where_translation_version_published_should_bump_only_its_entry():
    # Arrange
    captured: dict = {}
    client = GitHubContentsClient(
        http_client=httpx.Client(transport=_github_handler(captured)), token_service=StubTokenService()
    )
    version = _make_asset_and_version(slug="tafsir", name="1.1.0", language="az", is_source=False)

    # Act
    result = _make_updater(client).process_repository(_make_watched_repo(), version)

    # Assert
    assert result.action == "created"
    assert result.old_version == "1.0.0"
    assert captured["pr"]["title"] == "chore(deps): update tafsir-az to 1.1.0"
    assert captured["pr"]["head"] == "itqan-dependabot/assets/tafsir-az"
    committed_lockfile = next(item for item in captured["tree"]["tree"] if item["path"] == LOCKFILE_PATH)
    assert committed_lockfile["content"] == LOCKFILE.replace(b'version: "1.0.0"', b'version: "1.1.0"').decode()


def test_process_repository_where_language_not_in_manifest_should_skip():
    # Arrange
    captured: dict = {}
    client = GitHubContentsClient(
        http_client=httpx.Client(transport=_github_handler(captured)), token_service=StubTokenService()
    )
    version = _make_asset_and_version(slug="tafsir", name="2.0.0", language="fr", is_source=False)

    # Act
    result = _make_updater(client).process_repository(_make_watched_repo(), version)

    # Assert
    assert result.action == "skipped"
    assert result.reason == "asset_not_pinned"
    assert "pr" not in captured
