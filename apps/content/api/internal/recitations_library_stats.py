"""
Recitations library statistics for admin dashboard.

GET /cms-api/recitations/library-stats/ returns total_riwayas, total_reciters, total_recitations.
Cached in Redis with 12h TTL; invalidated on Riwayah, Reciter, or recitation Asset changes.
"""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from ninja import Schema

from apps.content.models import Asset, Reciter, Resource, Riwayah
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

# TODO: to not block merging contributor PR, consider moving this api to api/portal/ since it's only used for admin dashboard. And simplify api url to be .../recitations/stats/ to be simpler and consistent with other admin dashboard apis e.g. /reciters/stats/

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])

RECITATIONS_LIBRARY_STATS_CACHE_KEY = "recitations_library_stats:v1"
RECITATIONS_LIBRARY_STATS_TTL = 60 * 60 * 12  # 12 hours


class RecitationsLibraryStatsOut(Schema):
    """Key statistics for the recitations library (admin KPIs)."""

    total_riwayas: int
    total_reciters: int
    total_recitations: int


def _compute_library_stats() -> dict:
    """Compute counts from DB. Used on cache miss."""
    total_riwayas = Riwayah.objects.filter(is_active=True).count()
    total_reciters = Reciter.objects.filter(is_active=True).count()
    total_recitations = Asset.objects.filter(
        category=Resource.CategoryChoice.RECITATION,
    ).count()
    return {
        "total_riwayas": total_riwayas,
        "total_reciters": total_reciters,
        "total_recitations": total_recitations,
    }


@router.get("recitations/library-stats/", response=RecitationsLibraryStatsOut)
def recitations_library_stats(request: Request):
    """
    Return aggregated statistics for the recitations library (Riwayas, Reciters, Recitations).
    Cached for 12 hours; cache is invalidated when Riwayah, Reciter, or recitation Asset changes.
    """
    cached = cache.get(RECITATIONS_LIBRARY_STATS_CACHE_KEY)
    if cached is not None:
        return RecitationsLibraryStatsOut(**cached)
    stats = _compute_library_stats()
    cache.set(RECITATIONS_LIBRARY_STATS_CACHE_KEY, stats, timeout=RECITATIONS_LIBRARY_STATS_TTL)
    return stats


def _invalidate_library_stats_cache() -> None:
    cache.delete(RECITATIONS_LIBRARY_STATS_CACHE_KEY)


@receiver(post_save, sender=Riwayah)
@receiver(post_delete, sender=Riwayah)
def invalidate_library_stats_on_riwayah(sender, **kwargs):
    _invalidate_library_stats_cache()


@receiver(post_save, sender=Reciter)
@receiver(post_delete, sender=Reciter)
def invalidate_library_stats_on_reciter(sender, **kwargs):
    _invalidate_library_stats_cache()


@receiver(post_save, sender=Asset)
@receiver(post_delete, sender=Asset)
def invalidate_library_stats_on_asset(sender, instance, **kwargs):
    if instance.category == Resource.CategoryChoice.RECITATION:
        _invalidate_library_stats_cache()
