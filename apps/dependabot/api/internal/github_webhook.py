"""GitHub App webhook: the production consent entrypoint for #426.

GitHub signs every delivery (``X-Hub-Signature-256``); the signature is the
authentication — this route intentionally bypasses session auth
(``auth=None``) like other machine-to-machine routes. Supported events are
the installation lifecycle (created/deleted/suspend/unsuspend) and
installation_repositories (added/removed); everything else is acknowledged
and ignored. Nothing here opens PRs or writes to repositories — that is
#427's exclusive responsibility.
"""

import logging
from typing import Literal

from django.conf import settings as django_settings
from ninja import Schema

from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.dependabot.services.github_token import load_github_app_config
from apps.dependabot.services.github_webhook import GitHubWebhookService

router = ItqanRouter(tags=[NinjaTag.DEPENDABOT])
logger = logging.getLogger(__name__)


class WebhookOut(Schema):
    status: Literal["processed", "ignored"]
    event: str
    action: str | None = None
    affected: int = 0


@router.post(
    "dependabot/github/webhook/",
    auth=None,
    response={
        200: WebhookOut,
        400: NinjaErrorResponse[Literal["github_invalid_webhook_payload"]]
        | NinjaErrorResponse[Literal["dependabot_invalid_repository"]],
        401: NinjaErrorResponse[Literal["github_webhook_signature_invalid"]],
        500: NinjaErrorResponse[Literal["github_app_misconfigured"]],
    },
)
def github_webhook(request: Request):
    event = request.headers.get("X-GitHub-Event")
    if not load_github_app_config().enabled:
        logger.info("github_webhook: ignored while disabled [event=%s]", event or "unknown")
        return 200, WebhookOut(status="ignored", event=event or "unknown")
    secret = getattr(django_settings, "GITHUB_WEBHOOK_SECRET", "") or ""
    outcome = GitHubWebhookService().handle(
        event=event,
        payload=request.body,
        signature_header=request.headers.get("X-Hub-Signature-256"),
        secret=secret,
    )
    return 200, WebhookOut(
        status=outcome.status,
        event=outcome.event,
        action=outcome.action,
        affected=outcome.affected,
    )
