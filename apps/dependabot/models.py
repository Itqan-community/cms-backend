from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.users.models import User


class WatchedRepository(BaseModel):
    """A repository whose owner explicitly opted in to Itqan asset updates.

    One row per repository identity (``host`` + ``owner`` + ``repository_name``).
    Opt-out and suspension flip ``status``; rows are never deleted so the full
    opt-in history is preserved. V1 is GitHub-first: ``host`` is stored as
    metadata for future hosts, but only ``"github"`` is accepted — enforced
    by a database check constraint, not just application code. No secrets
    are stored here — installation tokens, JWTs, and private keys live only
    in settings (at rest) and in the process-local token cache (at runtime).
    """

    class HostChoice(models.TextChoices):
        GITHUB = "github", _("GitHub")

    class StatusChoice(models.TextChoices):
        OPTED_IN = "opted_in", _("Opted in")
        OPTED_OUT = "opted_out", _("Opted out")
        SUSPENDED = "suspended", _("Suspended")

    host = models.CharField(
        max_length=32,
        choices=HostChoice.choices,
        default=HostChoice.GITHUB,
        help_text="Git host holding the repository. Only GitHub is supported in V1.",
    )

    owner = models.CharField(max_length=255, help_text="Repository owner login (user or organization)")

    repository_name = models.CharField(max_length=255, help_text="Repository name without the owner prefix")

    installation_id = models.BigIntegerField(
        db_index=True,
        help_text="GitHub App installation ID that granted access to this repository",
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoice.choices,
        default=StatusChoice.OPTED_IN,
        db_index=True,
        help_text="Opt-in state. Only opted_in repositories are scanned for manifest updates.",
    )

    default_branch = models.CharField(
        max_length=255,
        default="main",
        help_text="Initial branch guess. Discovery resolves the repository's real GitHub default branch and overwrites this.",
    )

    last_manifest_sha = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Blob SHA of itqan-assets.yaml last seen by discovery (null = absent or never scanned)",
    )

    last_lockfile_sha = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Blob SHA of itqan-assets.lock last seen by discovery (null = absent or never scanned)",
    )

    last_checked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When manifest discovery last scanned this repository (null = never scanned)",
    )

    opted_in_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the latest opt-in happened. Re-opt-in refreshes this timestamp.",
    )

    opted_in_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependabot_opt_ins",
        help_text="Staff user who recorded the opt-in, if done through an authenticated surface.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["host", "owner", "repository_name"],
                name="unique_watched_repository",
            ),
            models.CheckConstraint(
                condition=models.Q(host="github"),
                name="watched_repository_github_only",
            ),
        ]
        indexes = [
            models.Index(fields=["host", "status"]),
        ]

    def __str__(self):
        return f"WatchedRepository(host={self.host}, owner={self.owner}, repository_name={self.repository_name})"

    @property
    def is_opted_in(self) -> bool:
        """Whether this repository is currently eligible for manifest discovery."""
        return self.status == self.StatusChoice.OPTED_IN
