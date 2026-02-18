from apps.content.models import ResourceVersion
from apps.content.tasks import send_resource_update_email


class ResourceService:
    def create_version(self, resource_version: ResourceVersion) -> ResourceVersion:
        """
        Creates a new ResourceVersion and notifies subscribed users.
        """
        if not resource_version.pk:
            resource_version.save()
            self._notify_subscribers(resource_version)
        return resource_version

    def _notify_subscribers(self, resource_version: ResourceVersion):
        """
        Notify users who have access to any asset within this resource.
        """
        send_resource_update_email.delay(resource_version.pk)
