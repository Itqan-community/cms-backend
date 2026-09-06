"""GitHub App webhook receiver helpers (installation lifecycle only).

This is the production consent entrypoint for #426: GitHub delivers
installation events here, the signature is verified, and the repositories
explicitly contained in each event are opted in or out through
:class:`WatchedRepositoryService`. The handler itself stays thin —
signature validation, JSON/event parsing, service calls — while all status
transitions live in the watched-repository service.

Supported events (everything else is acknowledged and ignored):

- ``installation``: ``created`` / ``deleted`` / ``suspend`` / ``unsuspend``
- ``installation_repositories``: ``added`` / ``removed``

Consent decisions encoded here:

- Uninstall (``installation.deleted``) means consent withdrawn, so rows
  become ``opted_out`` (history preserved). Reinstalling sends a new
  ``created`` event, which re-opts in explicitly.
- Suspension only flips currently ``opted_in`` rows (see
  ``suspend_installation``), so ``unsuspend`` can never revive an
  explicitly ``opted_out`` repository.
- No outbound GitHub API calls are made: every required fact (owner,
  repository names, installation ID) arrives inside the signed payload.

Security rules: the webhook secret is never logged; unverified payloads are
never processed; failures carry no secret material.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import logging
from typing import Literal

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.models import WatchedRepository
from apps.dependabot.services.watched_repositories import WatchedRepositoryService

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-Hub-Signature-256"
SIGNATURE_PREFIX = "sha256="

SUPPORTED_EVENTS = ("installation", "installation_repositories")

WebhookStatus = Literal["processed", "ignored"]


@dataclass(frozen=True)
class WebhookRepository:
    owner: str
    repository_name: str


@dataclass(frozen=True)
class WebhookEvent:
    event: str
    action: str | None
    installation_id: int
    repositories: tuple[WebhookRepository, ...]


@dataclass(frozen=True)
class WebhookOutcome:
    status: WebhookStatus
    event: str
    action: str | None
    affected: int


def verify_webhook_signature(*, secret: str, payload: bytes, signature_header: str | None) -> bool:
    """Verify the ``X-Hub-Signature-256`` header with a constant-time compare.

    Returns False for missing, malformed, or mismatching signatures — and
    whenever no secret is configured (an empty secret must never verify).
    Never raises and never logs the secret.
    """
    if not secret or not signature_header:
        return False
    if not signature_header.startswith(SIGNATURE_PREFIX):
        return False
    presented = signature_header[len(SIGNATURE_PREFIX) :]
    if not presented:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, presented)
    except TypeError:
        return False


def _parse_full_name(value: object) -> WebhookRepository:
    if not isinstance(value, str) or value.count("/") != 1:
        raise ItqanError(
            "github_invalid_webhook_payload",
            "GitHub webhook repository entries must look like owner/name.",
            400,
        )
    owner, repository_name = (part.strip() for part in value.split("/", 1))
    if not owner or not repository_name:
        raise ItqanError(
            "github_invalid_webhook_payload",
            "GitHub webhook repository entries must look like owner/name.",
            400,
        )
    return WebhookRepository(owner=owner, repository_name=repository_name)


def _parse_repo_list(value: object, *, field: str) -> tuple[WebhookRepository, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ItqanError(
            "github_invalid_webhook_payload",
            "GitHub webhook repository lists must be arrays.",
            400,
        )
    parsed: list[WebhookRepository] = []
    for entry in value:
        if not isinstance(entry, dict):
            raise ItqanError(
                "github_invalid_webhook_payload",
                "GitHub webhook repository entries must be objects.",
                400,
            )
        parsed.append(_parse_full_name(entry.get("full_name")))
    return tuple(parsed)


def parse_webhook_payload(*, event: str | None, payload: bytes) -> WebhookEvent:
    """Parse and shape-check a webhook delivery. Raises ItqanError (400) when malformed."""
    if not event:
        raise ItqanError(
            "github_invalid_webhook_payload",
            "GitHub webhook event header is missing.",
            400,
        )
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ItqanError(
            "github_invalid_webhook_payload",
            "GitHub webhook payload is not valid JSON.",
            400,
        ) from None
    if not isinstance(data, dict):
        raise ItqanError(
            "github_invalid_webhook_payload",
            "GitHub webhook payload must be a JSON object.",
            400,
        )
    action = data.get("action")
    if action is not None and not isinstance(action, str):
        raise ItqanError(
            "github_invalid_webhook_payload",
            "GitHub webhook action must be a string.",
            400,
        )
    installation = data.get("installation")
    if not isinstance(installation, dict):
        raise ItqanError(
            "github_invalid_webhook_payload",
            "GitHub webhook payload is missing the installation.",
            400,
        )
    installation_id = installation.get("id")
    if not isinstance(installation_id, int) or isinstance(installation_id, bool) or installation_id <= 0:
        raise ItqanError(
            "github_invalid_webhook_payload",
            "GitHub webhook installation ID must be a positive integer.",
            400,
        )
    repositories: tuple[WebhookRepository, ...] = ()
    if event == "installation":
        repositories = _parse_repo_list(data.get("repositories"), field="repositories")
    elif event == "installation_repositories":
        if action == "added":
            repositories = _parse_repo_list(data.get("repositories_added"), field="repositories_added")
        elif action == "removed":
            repositories = _parse_repo_list(data.get("repositories_removed"), field="repositories_removed")
    return WebhookEvent(
        event=event,
        action=action,
        installation_id=installation_id,
        repositories=repositories,
    )


class GitHubWebhookService:
    """Dispatch verified webhook events to opt-in transitions."""

    def __init__(self, watched_service: WatchedRepositoryService | None = None) -> None:
        self._watched = watched_service or WatchedRepositoryService()

    def handle(
        self,
        *,
        event: str | None,
        payload: bytes,
        signature_header: str | None,
        secret: str,
    ) -> WebhookOutcome:
        """Verify, parse, and apply one delivery. Never processes unverified data."""
        if not secret:
            raise ItqanError(
                "github_app_misconfigured",
                "GitHub webhook secret is not configured.",
                500,
            )
        if not verify_webhook_signature(secret=secret, payload=payload, signature_header=signature_header):
            logger.warning("github_webhook: rejected delivery [event=%s]", event or "unknown")
            raise ItqanError(
                "github_webhook_signature_invalid",
                "GitHub webhook signature is invalid.",
                401,
            )
        if event not in SUPPORTED_EVENTS:
            # Unsupported events are acknowledged without parsing: their
            # payloads carry no installation contract we understand.
            logger.info("github_webhook: ignored event [event=%s]", event or "unknown")
            return WebhookOutcome(status="ignored", event=event or "unknown", action=None, affected=0)
        parsed = parse_webhook_payload(event=event, payload=payload)
        return self._dispatch_outcome(parsed)

    def _dispatch_outcome(self, parsed: WebhookEvent) -> WebhookOutcome:
        """Apply one supported event. Unknown actions are safely ignored."""
        affected = self._dispatch(parsed)
        if affected < 0:
            logger.info(
                "github_webhook: ignored action [event=%s, action=%s]",
                parsed.event,
                parsed.action,
            )
            return WebhookOutcome(status="ignored", event=parsed.event, action=parsed.action, affected=0)
        logger.info(
            "github_webhook: processed [event=%s, action=%s, affected=%d]",
            parsed.event,
            parsed.action,
            affected,
        )
        return WebhookOutcome(status="processed", event=parsed.event, action=parsed.action, affected=affected)

    def _dispatch(self, parsed: WebhookEvent) -> int:
        """Apply one event. Returns affected-row count, or -1 when safely ignored."""
        host = WatchedRepository.HostChoice.GITHUB
        if parsed.event == "installation":
            if parsed.action == "created":
                # The install selection itself is the consent: opt in exactly
                # the listed repositories, never anything unlisted.
                for repo in parsed.repositories:
                    self._watched.opt_in(
                        host=host,
                        owner=repo.owner,
                        repository_name=repo.repository_name,
                        installation_id=parsed.installation_id,
                    )
                return len(parsed.repositories)
            if parsed.action == "deleted":
                # Uninstall withdraws consent: stop discovery but keep rows.
                return self._watched.opt_out_installation(host=host, installation_id=parsed.installation_id)
            if parsed.action == "suspend":
                return self._watched.suspend_installation(host=host, installation_id=parsed.installation_id)
            if parsed.action == "unsuspend":
                return self._watched.unsuspend_installation(host=host, installation_id=parsed.installation_id)
            return -1
        if parsed.event == "installation_repositories":
            if parsed.action == "added":
                for repo in parsed.repositories:
                    self._watched.opt_in(
                        host=host,
                        owner=repo.owner,
                        repository_name=repo.repository_name,
                        installation_id=parsed.installation_id,
                    )
                return len(parsed.repositories)
            if parsed.action == "removed":
                affected = 0
                for repo in parsed.repositories:
                    try:
                        self._watched.opt_out(host=host, owner=repo.owner, repository_name=repo.repository_name)
                    except ItqanError as exc:
                        # Removing an untracked repository is already the
                        # desired end state; anything else is a real error.
                        if exc.error_name != "dependabot_repository_not_found":
                            raise
                        continue
                    affected += 1
                return affected
            return -1
        return -1
