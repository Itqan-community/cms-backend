from __future__ import annotations

from datetime import datetime

from django.db.models import QuerySet
from django.utils import timezone

from apps.dependabot.models import WatchedRepository
from apps.users.models import User


class WatchedRepositoryRepository:
    """Data-access layer for watched-repository rows.

    Thin by design: identity lookups, status flips, and discovery-state
    writes. Opt-in semantics (idempotency, explicitness) live in the service
    layer; missing rows surface as ``None`` and are translated to
    ``ItqanError`` there.
    """

    def get_by_owner_repo(self, host: str, owner: str, repository_name: str) -> WatchedRepository | None:
        return WatchedRepository.objects.filter(host=host, owner=owner, repository_name=repository_name).first()

    def list_opted_in(self, host: str = WatchedRepository.HostChoice.GITHUB) -> QuerySet[WatchedRepository]:
        return WatchedRepository.objects.filter(
            host=host,
            status=WatchedRepository.StatusChoice.OPTED_IN,
        ).order_by("id")

    def create_or_update_opt_in(
        self,
        *,
        host: str,
        owner: str,
        repository_name: str,
        installation_id: int,
        default_branch: str = "main",
        opted_in_by: User | None = None,
    ) -> tuple[WatchedRepository, bool]:
        """Record an explicit opt-in, refreshing a previous row if one exists.

        Returns the row and whether it was created. Re-opt-in always flips
        the status back to ``opted_in`` and refreshes ``opted_in_at``.

        Explicit-consent path only: callers must represent a genuine opt-in
        (a staff-recorded owner request, or a GitHub install/add event).
        Automatic or background synchronization must never call this — it
        would silently re-enable ``opted_out`` rows. Sync paths use the
        read-only lookups plus :meth:`update_discovery_state`.
        """
        defaults: dict = {
            "installation_id": installation_id,
            "default_branch": default_branch,
            "status": WatchedRepository.StatusChoice.OPTED_IN,
            "opted_in_at": timezone.now(),
        }
        if opted_in_by is not None:
            defaults["opted_in_by"] = opted_in_by
        return WatchedRepository.objects.update_or_create(
            host=host,
            owner=owner,
            repository_name=repository_name,
            defaults=defaults,
        )

    def set_opt_out(self, host: str, owner: str, repository_name: str) -> WatchedRepository | None:
        """Flip a row to ``opted_out``, preserving its history. None if unknown."""
        watched = self.get_by_owner_repo(host, owner, repository_name)
        if watched is None:
            return None
        watched.status = WatchedRepository.StatusChoice.OPTED_OUT
        watched.save(update_fields=["status", "updated_at"])
        return watched

    def set_suspended(self, host: str, owner: str, repository_name: str) -> WatchedRepository | None:
        """Flip a row to ``suspended``, preserving its history. None if unknown."""
        watched = self.get_by_owner_repo(host, owner, repository_name)
        if watched is None:
            return None
        watched.status = WatchedRepository.StatusChoice.SUSPENDED
        watched.save(update_fields=["status", "updated_at"])
        return watched

    def opt_out_if_installation_matches(
        self, host: str, owner: str, repository_name: str, installation_id: int
    ) -> bool:
        """Atomically opt out only if the row still belongs to the installation.

        Single conditional ``UPDATE ... WHERE identity + installation_id``:
        a stale removal replayed after the repo re-opted-in under a newer
        installation matches nothing. Already-``opted_out`` rows are left
        alone. Returns True when a row transitioned.
        """
        updated = (
            WatchedRepository.objects.filter(
                host=host,
                owner=owner,
                repository_name=repository_name,
                installation_id=installation_id,
            )
            .exclude(status=WatchedRepository.StatusChoice.OPTED_OUT)
            .update(status=WatchedRepository.StatusChoice.OPTED_OUT, updated_at=timezone.now())
        )
        return updated > 0

    def set_installation_status(
        self,
        installation_id: int,
        *,
        host: str,
        expected_status: str | None,
        new_status: str,
        refresh_opt_in_at: bool = False,
    ) -> int:
        """Atomically flip one installation's rows in a single UPDATE statement.

        The expected current status is part of the WHERE clause, so concurrent
        deliveries cannot interleave between a read and a write. ``QuerySet.
        update()`` skips ``auto_now``, hence ``updated_at`` (and
        ``opted_in_at`` when restoring consent) is set explicitly. A None
        ``expected_status`` matches every status except ``new_status`` itself,
        keeping redeliveries idempotent. Returns transitioned rows.
        """
        rows = WatchedRepository.objects.filter(installation_id=installation_id, host=host)
        if expected_status is None:
            rows = rows.exclude(status=new_status)
        else:
            rows = rows.filter(status=expected_status)
        now = timezone.now()
        if refresh_opt_in_at:
            return rows.update(status=new_status, updated_at=now, opted_in_at=now)
        return rows.update(status=new_status, updated_at=now)

    def update_discovery_state(
        self,
        host: str,
        owner: str,
        repository_name: str,
        *,
        last_manifest_sha: str | None,
        last_lockfile_sha: str | None,
        last_checked_at: datetime,
        default_branch: str | None = None,
    ) -> WatchedRepository | None:
        """Record what discovery last saw. Status is left untouched. None if unknown.

        ``default_branch`` is optional: discovery passes the repository's
        real default branch once resolved (overwriting the ``"main"`` initial
        guess); when omitted the stored value is left unchanged.
        """
        watched = self.get_by_owner_repo(host, owner, repository_name)
        if watched is None:
            return None
        watched.last_manifest_sha = last_manifest_sha
        watched.last_lockfile_sha = last_lockfile_sha
        watched.last_checked_at = last_checked_at
        update_fields = ["last_manifest_sha", "last_lockfile_sha", "last_checked_at", "updated_at"]
        if default_branch is not None:
            watched.default_branch = default_branch
            update_fields.append("default_branch")
        watched.save(update_fields=update_fields)
        return watched
