from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache

from apps.publishers.models import Domain


@receiver(post_save, sender=Domain)
@receiver(post_delete, sender=Domain)
def clear_domain_cache(
    sender: type[Domain],
    instance: Domain,
    **kwargs: object
) -> None:

    cache.delete(f"x_tenant-{instance.domain}")