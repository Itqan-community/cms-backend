import logging

from apps.content.models import AssetVersion
from apps.content.tasks import send_asset_update_email

logger = logging.getLogger(__name__)


class AssetService:
    def create_version(self, asset_version: AssetVersion) -> AssetVersion:
        """
        Creates a new AssetVersion and notifies subscribed users.
        """
        if not asset_version.pk:
            asset_version.save()
            logger.info(
                f"Asset version created [asset_version_id={asset_version.pk}, asset_id={asset_version.asset_id}]"
            )
            self._notify_subscribers(asset_version)
        return asset_version

    def _notify_subscribers(self, asset_version: AssetVersion):
        """
        Notify users who have access to this asset.
        """
        send_asset_update_email.delay(asset_version.pk)
        logger.info(f"Asset update email queued [asset_version_id={asset_version.pk}]")
