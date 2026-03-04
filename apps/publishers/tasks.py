from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from .models import Publisher


@shared_task
def compute_publisher_stats_task():
    total_publishers = Publisher.objects.count()

    verified_publishers = Publisher.objects.filter(
        is_verified=True
    ).count()

    active_publishers = (
        Publisher.objects
        .filter(domains__is_active=True)
        .distinct()
        .count()
    )

    total_countries = (
        Publisher.objects
        .exclude(country="")
        .values("country")
        .distinct()
        .count()
    )

    stats = {
        "total_publishers": total_publishers,
        "active_publishers": active_publishers,
        "verified_publishers": verified_publishers,
        "total_countries": total_countries,
        "last_updated": timezone.now().isoformat(),
    }

    cache.set("publisher_stats", stats, timeout=None)

    return stats