from django.utils import timezone
from django.core.cache import cache
from apps.publishers.models import Publisher

CACHE_KEY_PUBLISHER_STATS = "publisher_stats"


def compute_publisher_stats_sync():
    total_publishers = Publisher.objects.count()
    active_publishers = Publisher.objects.filter(domains__is_active=True).distinct().count()
    verified_publishers = Publisher.objects.filter(is_verified=True).count()
    total_countries = Publisher.objects.values("country").distinct().count()

    stats = {
        "total_publishers": total_publishers,
        "active_publishers": active_publishers,
        "verified_publishers": verified_publishers,
        "total_countries": total_countries,
        "last_updated": timezone.now().isoformat(),
    }

    cache.set(CACHE_KEY_PUBLISHER_STATS, stats, timeout=None)

    return stats