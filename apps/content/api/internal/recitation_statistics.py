import hashlib
import json
import logging

from django.core.cache import cache
from ninja import Schema

from apps.content.models import Asset, Reciter, Resource
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

logger = logging.getLogger(__name__)

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])

STATISTICS_CACHE_TTL = 60 * 15  # 15 minutes


class RecitationStatisticsOut(Schema):
    """Response schema for recitation statistics overview."""

    total_riwayahs: int
    total_reciters: int
    total_recitations: int


def _build_cache_key(publisher_id: int | None) -> str:
    """Build a deterministic cache key for recitation statistics."""
    raw = f"recitation_stats:publisher={publisher_id or 'all'}"
    return hashlib.md5(raw.encode()).hexdigest()


@router.get("recitations/statistics/", response=RecitationStatisticsOut)
def recitation_statistics(request: Request):
    """
    Returns aggregated statistics for the audio recitations library.

    Statistics include:
    - Total number of Riwayas (transmission traditions)
    - Total number of Reciters
    - Total number of Recitations (audio assets)

    Results are cached with a 15-minute TTL for performance.

    Closes #188
    """
    publisher = getattr(request, "publisher", None)
    publisher_id = publisher.id if publisher else None
    cache_key = _build_cache_key(publisher_id)

    # Try cache first
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("Recitation statistics cache hit for key=%s", cache_key)
        return RecitationStatisticsOut(**cached)

    # Build publisher filter
    publisher_q = request.publisher_q("resource__publisher")

    # Base filter for READY recitation assets
    base_filter = {
        "category": Resource.CategoryChoice.RECITATION,
        "resource__category": Resource.CategoryChoice.RECITATION,
        "resource__status": Resource.StatusChoice.READY,
    }

    # Count distinct reciters with READY recitation assets
    total_reciters = (
        Reciter.objects.filter(
            is_active=True,
            assets__category=Resource.CategoryChoice.RECITATION,
            assets__resource__category=Resource.CategoryChoice.RECITATION,
            assets__resource__status=Resource.StatusChoice.READY,
        )
        .filter(publisher_q)
        .distinct()
        .count()
    )

    # Count distinct riwayahs with READY recitation assets
    from apps.content.models import Riwayah

    riwayah_publisher_q = request.publisher_q("assets__resource__publisher")
    total_riwayahs = (
        Riwayah.objects.filter(
            is_active=True,
            assets__category=Resource.CategoryChoice.RECITATION,
            assets__resource__category=Resource.CategoryChoice.RECITATION,
            assets__resource__status=Resource.StatusChoice.READY,
        )
        .filter(riwayah_publisher_q)
        .distinct()
        .count()
    )

    # Count total READY recitation assets
    total_recitations = (
        Asset.objects.filter(**base_filter)
        .filter(publisher_q)
        .distinct()
        .count()
    )

    stats = {
        "total_riwayahs": total_riwayahs,
        "total_reciters": total_reciters,
        "total_recitations": total_recitations,
    }

    # Cache the result
    cache.set(cache_key, stats, STATISTICS_CACHE_TTL)
    logger.info(
        "Recitation statistics computed and cached: reciters=%d, riwayahs=%d, recitations=%d",
        total_reciters,
        total_riwayahs,
        total_recitations,
    )

    return RecitationStatisticsOut(**stats)
