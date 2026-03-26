from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from ninja import Schema

from apps.content.models import Reciter
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

# TODO: to not block merging contributor PR, consider moving this api to api/portal/ since it's only used for admin dashboard.

router = ItqanRouter(tags=[NinjaTag.RECITERS])

RECITER_STATS_CACHE_KEY = "reciter_stats:v1"
RECITER_STATS_TTL = 60 * 60 * 12  # 12 hours


class ReciterStatsAggregationOut(Schema):
    nationalities: int
    contemporary_reciters: int
    registered_reciters: int


@router.get("reciters/stats/", response=ReciterStatsAggregationOut)
def reciter_stats(request: Request):
    cached = cache.get(RECITER_STATS_CACHE_KEY)
    if cached is not None:
        return ReciterStatsAggregationOut(**cached)
    stats = Reciter.objects.aggregate(
        registered_reciters=Count(
            "id",
            filter=Q(is_active=True),
            distinct=True,
        ),
        contemporary_reciters=Count(
            "id",
            filter=Q(is_contemporary=True, is_active=True),
            distinct=True,
        ),
        nationalities=Count(
            "nationality",
            filter=Q(is_active=True),
            distinct=True,
        ),
    )

    cache.set(RECITER_STATS_CACHE_KEY, stats, timeout=RECITER_STATS_TTL)
    return stats


@receiver(post_save, sender=Reciter)
@receiver(post_delete, sender=Reciter)
def invalidate_reciter_stats_cache(sender, **kwargs):
    cache.delete(RECITER_STATS_CACHE_KEY)
