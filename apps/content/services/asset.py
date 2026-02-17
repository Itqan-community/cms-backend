from apps.content.models import AssetVersion
from apps.content.tasks import send_asset_update_email


class AssetService:
    def create_version(self, asset_version: AssetVersion) -> AssetVersion:
        """
        Creates a new AssetVersion and notifies subscribed users.
        """
        if not asset_version.pk:
            asset_version.save()
            self._notify_subscribers(asset_version)
        return asset_version

    def _notify_subscribers(self, asset_version: AssetVersion):
        """
        Notify users who have access to this asset.
        """
        send_asset_update_email.delay(asset_version.pk)
