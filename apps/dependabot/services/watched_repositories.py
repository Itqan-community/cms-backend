"""Opt-in semantics for watched repositories.

Explicit opt-in is required: rows are only ever created through
:meth:`WatchedRepositoryService.opt_in`. Opt-out and suspension flip the
status in place — rows are never deleted — and only ``opted_in`` rows are
eligible for manifest discovery. This service is pure database access (no
network), so it is intentionally not gated on ``ENABLE_ITQAN_DEPENDABOT``;
that flag gates GitHub traffic in later phases.
"""

from __future__ import annotations

from datetime import UTC, datetime
import re

from django.utils import timezone

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.models import WatchedRepository
from apps.dependabot.repositories.watched_repository import WatchedRepositoryRepository
from apps.users.models import User

_SHA_RE = re.compile(r"^[0-9a-fA-F]{1,64}$")
# Git blob SHAs as returned by the GitHub Contents API ``sha`` field are
# SHA-1 today (40 lowercase hex chars). The 64-char ceiling leaves room for
# a future SHA-256 object format (64 hex); both are hex, so anything else is
# rejected as malformed rather than stored.


def _validate_host(host: str) -> str:
    if host != WatchedRepository.HostChoice.GITHUB:
        raise ItqanError(
            "dependabot_invalid_repository",
            "Only the 'github' host is supported.",
            400,
        )
    return host


def _validate_name(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "/" in value or len(value) > 255:
        raise ItqanError(
            "dependabot_invalid_repository",
            "Repository owner and name must be non-empty strings without slashes.",
            400,
        )
    return value


def _validate_branch(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 255:
        raise ItqanError(
            "dependabot_invalid_repository",
            "Default branch must be a non-empty string.",
            400,
        )
    return value


def _validate_installation_id(installation_id: int) -> int:
    if not isinstance(installation_id, int) or isinstance(installation_id, bool) or installation_id <= 0:
        raise ItqanError(
            "dependabot_invalid_repository",
            "GitHub installation ID must be a positive integer.",
            400,
        )
    return installation_id


def _validate_sha(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA_RE.match(value):
        raise ItqanError(
            "dependabot_invalid_repository",
            "Discovery SHAs must be hex strings when present.",
            400,
        )
    return value


def _coerce_aware(moment: datetime | None) -> datetime:
    if moment is None:
        return timezone.now()
    if moment.tzinfo is None or moment.utcoffset() is None:
        return moment.replace(tzinfo=UTC)
    return moment


class WatchedRepositoryService:
    """Enforce opt-in rules on top of :class:`WatchedRepositoryRepository`."""

    def __init__(self, repo: WatchedRepositoryRepository | None = None) -> None:
        self.repo = repo or WatchedRepositoryRepository()

    def opt_in(
        self,
        *,
        host: str = WatchedRepository.HostChoice.GITHUB,
        owner: str,
        repository_name: str,
        installation_id: int,
        default_branch: str = "main",
        opted_in_by: User | None = None,
    ) -> WatchedRepository:
        """Record an explicit opt-in. Idempotent: repeated calls refresh the row.

        The only legitimate future callers are explicit-consent surfaces: a
        portal action where staff records an owner's request, or a GitHub
        install/add webhook event (the install action itself is the consent).
        Must never be called from background sync or discovery loops.
        """
        _validate_host(host)
        _validate_name(owner, field="owner")
        _validate_name(repository_name, field="repository_name")
        _validate_installation_id(installation_id)
        _validate_branch(default_branch)
        watched, _ = self.repo.create_or_update_opt_in(
            host=host,
            owner=owner,
            repository_name=repository_name,
            installation_id=installation_id,
            default_branch=default_branch,
            opted_in_by=opted_in_by,
        )
        return watched

    def opt_out(self, *, host: str, owner: str, repository_name: str) -> WatchedRepository:
        """Flip a row to ``opted_out``, preserving its history."""
        watched = self._get_existing(host=host, owner=owner, repository_name=repository_name)
        result = self.repo.set_opt_out(watched.host, watched.owner, watched.repository_name)
        assert result is not None  # fetched above; races resolve as a later opt-in, not a loss
        return result

    def suspend(self, *, host: str, owner: str, repository_name: str) -> WatchedRepository:
        """Flip a row to ``suspended`` (e.g. installation suspended on GitHub's side)."""
        watched = self._get_existing(host=host, owner=owner, repository_name=repository_name)
        result = self.repo.set_suspended(watched.host, watched.owner, watched.repository_name)
        assert result is not None  # fetched above; races resolve as a later opt-in, not a loss
        return result

    def suspend_installation(self, *, host: str, installation_id: int) -> int:
        """Suspend one installation's repositories without touching explicit opt-outs.

        Only currently opted-in rows flip to suspended, so a later unsuspend
        can never revive a repository whose owner explicitly opted out.
        Returns the number of rows transitioned.
        """
        _validate_host(host)
        _validate_installation_id(installation_id)
        transitioned = 0
        rows = self.repo.list_by_installation(installation_id).filter(
            host=host,
            status=WatchedRepository.StatusChoice.OPTED_IN,
        )
        for watched in rows:
            if self.repo.set_suspended(watched.host, watched.owner, watched.repository_name) is not None:
                transitioned += 1
        return transitioned

    def unsuspend_installation(self, *, host: str, installation_id: int) -> int:
        """Restore a previously suspended installation to opted-in.

        Only suspended rows are restored; opted-out rows are never revived —
        an explicit opt-out outlives any suspension cycle. Returns the number
        of rows transitioned.
        """
        _validate_host(host)
        _validate_installation_id(installation_id)
        transitioned = 0
        rows = self.repo.list_by_installation(installation_id).filter(
            host=host,
            status=WatchedRepository.StatusChoice.SUSPENDED,
        )
        for watched in rows:
            self.opt_in(
                host=watched.host,
                owner=watched.owner,
                repository_name=watched.repository_name,
                installation_id=installation_id,
            )
            transitioned += 1
        return transitioned

    def opt_out_installation(self, *, host: str, installation_id: int) -> int:
        """Withdraw a whole installation (App uninstalled): every row becomes
        opted_out with history preserved. Reinstalling re-opts in explicitly
        through a new installation event. Returns rows transitioned."""
        _validate_host(host)
        _validate_installation_id(installation_id)
        transitioned = 0
        for watched in (
            self.repo.list_by_installation(installation_id)
            .filter(host=host)
            .exclude(status=WatchedRepository.StatusChoice.OPTED_OUT)
        ):
            if self.repo.set_opt_out(watched.host, watched.owner, watched.repository_name) is not None:
                transitioned += 1
        return transitioned

    def require_opted_in(self, *, host: str, owner: str, repository_name: str) -> WatchedRepository:
        """Return the row if it is currently opted in, else raise."""
        watched = self._get_existing(host=host, owner=owner, repository_name=repository_name)
        if not watched.is_opted_in:
            raise ItqanError(
                "dependabot_repository_not_found",
                f"Repository {owner}/{repository_name} is not opted in to Itqan asset updates.",
                404,
            )
        return watched

    def record_discovery(
        self,
        *,
        host: str,
        owner: str,
        repository_name: str,
        last_manifest_sha: str | None,
        last_lockfile_sha: str | None,
        last_checked_at: datetime | None = None,
        default_branch: str | None = None,
    ) -> WatchedRepository:
        """Persist what discovery last saw. Only opted-in rows are updated.

        ``default_branch`` carries the repository's real default branch once
        discovery resolves it (replacing the ``"main"`` initial guess); omit
        it to leave the stored value unchanged.
        """
        watched = self.require_opted_in(host=host, owner=owner, repository_name=repository_name)
        if default_branch is not None:
            _validate_branch(default_branch)
        result = self.repo.update_discovery_state(
            watched.host,
            watched.owner,
            watched.repository_name,
            last_manifest_sha=_validate_sha(last_manifest_sha, field="last_manifest_sha"),
            last_lockfile_sha=_validate_sha(last_lockfile_sha, field="last_lockfile_sha"),
            last_checked_at=_coerce_aware(last_checked_at),
            default_branch=default_branch,
        )
        assert result is not None  # fetched above; races resolve as a later opt-in, not a loss
        return result

    def _get_existing(self, *, host: str, owner: str, repository_name: str) -> WatchedRepository:
        _validate_host(host)
        _validate_name(owner, field="owner")
        _validate_name(repository_name, field="repository_name")
        watched = self.repo.get_by_owner_repo(host, owner, repository_name)
        if watched is None:
            raise ItqanError(
                "dependabot_repository_not_found",
                f"Repository {owner}/{repository_name} is not opted in to Itqan asset updates.",
                404,
            )
        return watched
