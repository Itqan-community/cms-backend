from __future__ import annotations

import logging

from apps.content.models import AssetAccess, AssetVersion
from apps.core.services.email import email_service

logger = logging.getLogger(__name__)


class AssetVersionNotifier:
    def notify_new_version(self, asset_version_id: int) -> None:
        logger.info(f"Notifying subscribers [asset_version_id={asset_version_id}]")

        try:
            asset_version = AssetVersion.objects.select_related("asset").get(pk=asset_version_id)
        except AssetVersion.DoesNotExist:
            logger.warning(f"AssetVersion not found, skipping email [asset_version_id={asset_version_id}]")
            return

        is_first_version = (
            not AssetVersion.objects.filter(asset=asset_version.asset).exclude(pk=asset_version_id).exists()
        )
        if is_first_version:
            logger.info(f"First version for asset, skipping notification [asset_version_id={asset_version_id}]")
            return

        users = (
            AssetAccess.objects.filter(asset=asset_version.asset)
            .select_related("user")
            .values_list("user__email", flat=True)
            .distinct()
        )

        if not users:
            logger.info(f"No subscribers to notify [asset_version_id={asset_version_id}]")
            return

        subject = f"New Update for {asset_version.asset.name}"
        context = {
            "asset_name": asset_version.asset.name,
            "version": asset_version.name,
            "summary": asset_version.summary,
        }

        email_service.send_email(
            subject=subject,
            recipients=list(users),
            template="emails/asset_update.html",
            context=context,
        )
        logger.info(
            f"Asset version notification sent [asset_version_id={asset_version_id}, recipients={len(list(users))}]"
        )
