from django.core.cache import cache

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


@router.get("publishers/stats/", description="Get publisher statistics")
def get_publisher_stats(request: Request):
    stats = cache.get("publisher_stats")

    if not stats:
        from apps.publishers.tasks import compute_publisher_stats_task
        stats = compute_publisher_stats_task()

    return stats