from django.core.cache import cache
from ninja import Schema

from apps.content.models import Reciter
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITERS])


class RecitersStatsOut(Schema):
    total_reciters: int
    total_nationalities: int
    contemporary_reciters: int


CACHE_KEY = "reciters_stats"
CACHE_TTL = 3600  # 1 hour


@router.get("reciters/stats/", response=RecitersStatsOut, auth=None)
def get_reciters_stats(request: Request):
    cached = cache.get(CACHE_KEY)
    if cached:
        return cached

    qs = Reciter.objects.filter(is_active=True)
    stats = {
        "total_reciters": qs.count(),
        "total_nationalities": qs.exclude(nationality="").values("nationality").distinct().count(),
        "contemporary_reciters": qs.filter(is_contemporary=True).count(),
    }
    cache.set(CACHE_KEY, stats, timeout=CACHE_TTL)
    return stats
