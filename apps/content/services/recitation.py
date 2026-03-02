from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.core.cache import cache

if TYPE_CHECKING:
    from django.db.models import Q, QuerySet

    from apps.content.models import Asset, RecitationSurahTrack
    from apps.content.repositories.base import BaseRecitationRepository

logger = logging.getLogger(__name__)

STATS_CACHE_TTL = 60 * 5  # 5 minutes


class RecitationService:
    def __init__(self, repo: BaseRecitationRepository) -> None:
        self.repo = repo

    def get_all_recitations(
        self, publisher_q: Q, filters: Any = None, annotate_surahs_count: bool = False
    ) -> QuerySet[Asset]:
        """
        Business Logic: Retrieve all recitations for a specific publisher/tenant.
        """
        # Convert filter object to dictionary for the repository
        filters_dict = filters.model_dump(exclude_none=True) if filters and hasattr(filters, "model_dump") else {}

        return self.repo.list_recitations_qs(
            publisher_q, filters_dict=filters_dict, annotate_surahs_count=annotate_surahs_count
        )

    def get_asset_tracks(
        self, asset_id: int, publisher_q: Q, prefetch_timings: bool = False
    ) -> QuerySet[RecitationSurahTrack]:
        """
        Business Logic: Retrieve tracks for a specific asset if it belongs to the publisher.
        """
        return self.repo.list_recitation_tracks_for_asset(
            asset_id, publisher_q=publisher_q, prefetch_timings=prefetch_timings
        )

    def get_all_reciters(self, publisher_q: Q, filters: Any = None) -> QuerySet:
        """
        Business Logic: Retrieve all reciters that have READY recitations for a specific publisher/tenant.
        """
        # Convert filter object to dictionary for the repository
        filters_dict = filters.model_dump(exclude_none=True) if filters and hasattr(filters, "model_dump") else {}

        return self.repo.list_reciters_qs(publisher_q, filters_dict=filters_dict)

    def get_recitation_statistics(self, publisher_q: Q, publisher_id: int | None = None) -> dict[str, int]:
        """
        Business Logic: Return cached aggregate statistics for the recitation library.
        Cache is keyed per publisher to maintain tenant isolation.
        """
        cache_key = f"recitation_stats-{publisher_id or 'all'}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        stats = self.repo.get_recitation_statistics(publisher_q)
        cache.set(cache_key, stats, timeout=STATS_CACHE_TTL)
        return stats
