from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models import Q, QuerySet

    from apps.content.models import Asset, Qiraah, RecitationSurahTrack, Riwayah


class BaseRecitationRepository(ABC):
    @abstractmethod
    def list_recitations_qs(
        self, publisher_q: Q, filters_dict: dict[str, Any], annotate_surahs_count: bool = False
    ) -> QuerySet[Asset]:
        """
        Returns a queryset of recitation assets.
        """
        pass

    @abstractmethod
    def get_recitation_asset(self, asset_id: int, publisher_q: Q) -> dict[str, Any] | None:
        """
        Retrieves a single recitation asset by ID.
        """
        pass

    @abstractmethod
    def list_recitation_tracks_for_asset(
        self, asset_id: int, publisher_q: Q, prefetch_timings: bool = False
    ) -> QuerySet[RecitationSurahTrack]:
        """
        Returns a list of tracks for a given asset ID.
        """
        pass

    @abstractmethod
    def list_reciters_qs(self, publisher_q: Q, filters_dict: dict[str, Any]) -> QuerySet:
        """
        Returns a queryset of Reciter objects that have READY recitation assets.
        """
        pass

    @abstractmethod
    def list_riwayahs_qs(self, publisher_q: Q, filters_dict: dict[str, Any]) -> QuerySet[Riwayah]:
        """
        Returns a queryset of Riwayah objects that have READY recitation assets.
        """
        pass

    @abstractmethod
    def list_qiraahs_qs(self, publisher_q: Q, filters_dict: dict[str, Any]) -> QuerySet[Qiraah]:
        """
        Returns a queryset of Qiraah objects that have READY recitation assets through riwayahs.
        """
        pass
