from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.content.models import Asset, RecitationSurahTrack, Resource
from apps.content.repositories.base import BaseRecitationRepository

if TYPE_CHECKING:
    from django.db.models import Q, QuerySet


class RecitationRepository(BaseRecitationRepository):
    def __init__(self) -> None:
        self.asset_model = Asset
        self.track_model = RecitationSurahTrack

    def list_recitations_qs(
        self, publisher_q: Q, filters_dict: dict[str, Any], annotate_surahs_count: bool = False
    ) -> QuerySet[Asset]:
        """
        Returns a queryset of Asset objects.
        """
        qs = self.asset_model.objects.select_related("resource", "reciter", "riwayah").filter(
            publisher_q,
            category=Asset.CategoryChoice.RECITATION,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
        )

        if annotate_surahs_count:
            from django.db.models import Count

            qs = qs.annotate(surahs_count=Count("recitation_tracks"))

        return qs

    def get_recitation_asset(self, asset_id: int, publisher_q: Q) -> dict[str, Any] | None:
        try:
            asset = self.get_asset_object(asset_id, publisher_q)
            if not asset:
                return None
            return {
                "id": asset.id,
                "name": asset.name,
                "description": asset.description,
            }
        except Asset.DoesNotExist:
            return None

    def get_asset_object(self, asset_id: int, publisher_q: Q) -> Asset | None:
        """Utility for internal use within the service if needed"""
        try:
            return self.asset_model.objects.select_related("resource", "resource__publisher").get(
                publisher_q,
                id=asset_id,
                category=Asset.CategoryChoice.RECITATION,
                resource__category=Resource.CategoryChoice.RECITATION,
                resource__status=Resource.StatusChoice.READY,
            )
        except Asset.DoesNotExist:
            return None

    def list_recitation_tracks_for_asset(
        self, asset_id: int, prefetch_timings: bool = False
    ) -> QuerySet[RecitationSurahTrack]:
        qs = (
            self.track_model.objects.select_related("asset__reciter").filter(asset_id=asset_id).order_by("surah_number")
        )
        if prefetch_timings:
            qs = qs.prefetch_related("ayah_timings")
        return qs
