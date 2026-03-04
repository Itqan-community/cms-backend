from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from apps.publishers.models import Domain


@receiver(post_save, sender=Domain)
def clear_domain_cache(sender, instance, **kwargs):
    cache.delete(f"x_tenant-{instance.domain}")