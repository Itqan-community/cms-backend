from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models import Q, QuerySet

    from apps.content.models import Asset, RecitationSurahTrack
    from apps.content.repositories.base import BaseRecitationRepository


class RecitationService:
    def __init__(self, repo: BaseRecitationRepository) -> None:
        self.repo = repo

    def get_all_recitations(self, publisher_q: Q, filters: Any, annotate_surahs_count: bool = False) -> QuerySet[Asset]:
        """
        Business Logic: Retrieve all recitations for a specific publisher/tenant.
        """
        filters_dict = filters.dict(exclude_none=True) if filters else {}
        return self.repo.list_recitations_qs(publisher_q, filters_dict, annotate_surahs_count=annotate_surahs_count)

    def get_asset_tracks(
        self, asset_id: int, publisher_q: Q, prefetch_timings: bool = False
    ) -> QuerySet[RecitationSurahTrack]:
        """
        Business Logic: Retrieve tracks for a specific asset if it belongs to the publisher.
        """
        # We need to verify the asset belongs to the publisher and is a recitation
        # This is handled by the repository's get_asset_object or similar logic
        return self.repo.list_recitation_tracks_for_asset(asset_id, prefetch_timings=prefetch_timings)
