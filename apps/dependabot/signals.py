"""Signal receivers for triggering Dependabot PR automation upon asset version publication."""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.content.models import AssetVersion, VersionStateChoice

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AssetVersion)
def on_asset_version_published(
    sender,
    instance: AssetVersion,
    created: bool,
    update_fields=None,
    **kwargs,
) -> None:
    """Trigger Dependabot PR updates when an AssetVersion is published."""
    if instance.state != VersionStateChoice.PUBLISHED:
        return

    # Check update_fields to avoid triggering on unrelated field saves
    if update_fields is not None and not ({"state", "name", "summary"} & set(update_fields)):
        return

    from apps.dependabot.services.github_token import load_github_app_config

    if not load_github_app_config().enabled:
        return

    from apps.dependabot.tasks import dispatch_dependabot_updates_for_version

    logger.info(
        "dependabot_signal: queuing dependabot update for published version [asset_version_id=%d, asset=%s, version=%s]",
        instance.pk,
        instance.asset_id,
        instance.name,
    )
    transaction.on_commit(lambda version_id=instance.pk: dispatch_dependabot_updates_for_version.delay(version_id))
