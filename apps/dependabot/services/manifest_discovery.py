"""Manifest discovery orchestration for opted-in repositories.

Read-only end to end: resolve the repository's actual default branch,
fetch the two V1 root files (``itqan-assets.yaml``, ``itqan-assets.lock``),
classify the pair into a lockfile state, and persist the observation
(SHAs, branch, timestamp). Consent and status are never modified here, and
nothing is written to the repository — no commits, branches, or PRs, which
remain #427's exclusive responsibility.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.models import WatchedRepository
from apps.dependabot.services.github_client import LOCKFILE_PATH, MANIFEST_PATH, DiscoveredFile, GitHubContentsClient
from apps.dependabot.services.github_token import load_github_app_config
from apps.dependabot.services.manifest_parse import (
    DiscoveryClassification,
    DiscoveryState,
    ParsedLockfile,
    ParsedManifest,
    classify_discovery,
)
from apps.dependabot.services.watched_repositories import WatchedRepositoryService


@dataclass(frozen=True)
class DiscoveryResult:
    """The outcome of one discovery run over a watched repository."""

    state: DiscoveryState
    owner: str
    repository_name: str
    default_branch: str
    manifest_sha: str | None
    lockfile_sha: str | None
    manifest: ParsedManifest | None
    lockfile: ParsedLockfile | None


class ManifestDiscoveryService:
    """Discover and classify the manifest pair of one opted-in repository.

    Args:
        contents_client: Read-only GitHub client. Tests inject one backed
            by ``httpx.MockTransport``.
        watched_service: Opt-in persistence gateway. Defaults to a plain
            :class:`WatchedRepositoryService`.
        clock: Optional clock for ``last_checked_at``. Defaults to the wall
            clock; tests inject a manual clock.
    """

    def __init__(
        self,
        *,
        contents_client: GitHubContentsClient | None = None,
        watched_service: WatchedRepositoryService | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._contents = contents_client or GitHubContentsClient()
        self._watched = watched_service or WatchedRepositoryService()
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(tz=UTC))

    def discover(self, *, host: str, owner: str, repository_name: str) -> DiscoveryResult:
        """Run discovery for one repository and persist the observation.

        Gate order is deliberate: feature flag, then opt-in consent, then
        network. Anything failing before classification persists nothing.
        """
        if not load_github_app_config().enabled:
            raise ItqanError(
                "github_dependabot_disabled",
                "Itqan Dependabot updater is disabled.",
                503,
            )
        watched = self._watched.require_opted_in(host=host, owner=owner, repository_name=repository_name)

        metadata = self._contents.get_repository(
            owner=watched.owner,
            repository_name=watched.repository_name,
            installation_id=watched.installation_id,
        )
        manifest_file = self._contents.get_file(
            owner=watched.owner,
            repository_name=watched.repository_name,
            installation_id=watched.installation_id,
            path=MANIFEST_PATH,
            ref=metadata.default_branch,
        )
        lockfile_file = self._contents.get_file(
            owner=watched.owner,
            repository_name=watched.repository_name,
            installation_id=watched.installation_id,
            path=LOCKFILE_PATH,
            ref=metadata.default_branch,
        )

        classification = classify_discovery(manifest=manifest_file, lockfile=lockfile_file)
        self._persist_observation(watched, metadata.default_branch, manifest_file, lockfile_file)
        return DiscoveryResult(
            state=classification.state,
            owner=watched.owner,
            repository_name=watched.repository_name,
            default_branch=metadata.default_branch,
            manifest_sha=manifest_file.sha,
            lockfile_sha=lockfile_file.sha,
            manifest=classification.manifest,
            lockfile=classification.lockfile,
        )

    def classify_pair(self, *, manifest: DiscoveredFile, lockfile: DiscoveredFile) -> DiscoveryClassification:
        """Classify a manifest/lockfile pair without network or persistence.

        Thin wrapper over :func:`classify_discovery` so tests and future
        callers share one entry point for the pure state machine.
        """
        return classify_discovery(manifest=manifest, lockfile=lockfile)

    def _persist_observation(
        self,
        watched: WatchedRepository,
        default_branch: str,
        manifest_file: DiscoveredFile,
        lockfile_file: DiscoveredFile,
    ) -> None:
        checked_at = self._clock()
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            checked_at = checked_at.replace(tzinfo=UTC)
        self._watched.record_discovery(
            host=watched.host,
            owner=watched.owner,
            repository_name=watched.repository_name,
            last_manifest_sha=manifest_file.sha,
            last_lockfile_sha=lockfile_file.sha,
            last_checked_at=checked_at,
            default_branch=default_branch,
        )
