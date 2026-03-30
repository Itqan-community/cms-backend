from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.publishers.models import Domain


@receiver(post_save, sender=Domain)
@receiver(post_delete, sender=Domain)
def clear_domain_cache(sender: type[Domain], instance: Domain, **kwargs: object) -> None:
    from apps.publishers.tasks import compute_publisher_stats_task

    cache.delete(f"x_tenant-{instance.domain}")
    compute_publisher_stats_task.delay()
