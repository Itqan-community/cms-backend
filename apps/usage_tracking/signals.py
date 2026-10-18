from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.usage_tracking.services.usage_apps import app_for_key
from apps.users.models import APIKey


@receiver(post_save, sender=APIKey, dispatch_uid="usage_tracking_usage_app_for_key")
def create_usage_app(sender, instance: APIKey, created: bool, raw: bool = False, **kwargs) -> None:
    if created and not raw:
        app_for_key(instance)
