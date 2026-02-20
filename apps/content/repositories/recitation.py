from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import Count, Q

from apps.content.models import Asset, Qiraah, RecitationSurahTrack, Reciter, Resource, Riwayah
from apps.content.repositories.base import BaseRecitationRepository

if TYPE_CHECKING:
    from django.db.models import QuerySet


class RecitationRepository(BaseRecitationRepository):
    def __init__(self) -> None:
        self.asset_model = Asset
        self.track_model = RecitationSurahTrack
        self.riwayah_model = Riwayah
        self.qiraah_model = Qiraah

    def list_recitations_qs(
        self, publisher_q: Q, filters_dict: dict[str, Any], annotate_surahs_count: bool = False
    ) -> QuerySet[Asset]:
        """
        Returns a queryset of Asset objects.
        """
        qs = self.asset_model.objects.select_related("resource", "reciter", "riwayah", "qiraah").filter(
            publisher_q,
            category=Resource.CategoryChoice.RECITATION,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
        )

        if filters_dict:
            if ids := filters_dict.get("id"):
                qs = qs.filter(id__in=ids)
            if reciter_ids := filters_dict.get("reciter_id"):
                qs = qs.filter(reciter_id__in=reciter_ids)
            if riwayah_ids := filters_dict.get("riwayah_id"):
                qs = qs.filter(riwayah_id__in=riwayah_ids)
            if qiraah_ids := filters_dict.get("qiraah_id"):
                qs = qs.filter(qiraah_id__in=qiraah_ids)
            if publisher_ids := filters_dict.get("publisher_id"):
                qs = qs.filter(resource__publisher_id__in=publisher_ids)
            if madd_levels := filters_dict.get("madd_level"):
                qs = qs.filter(madd_level__in=madd_levels)
            if meem_behaviours := filters_dict.get("meem_behaviour"):
                qs = qs.filter(meem_behaviour__in=meem_behaviours)

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
                category=Resource.CategoryChoice.RECITATION,
                resource__category=Resource.CategoryChoice.RECITATION,
                resource__status=Resource.StatusChoice.READY,
            )
        except Asset.DoesNotExist:
            return None

    def list_recitation_tracks_for_asset(
        self, asset_id: int, publisher_q: Q, prefetch_timings: bool = False
    ) -> QuerySet[RecitationSurahTrack]:
        qs = (
            self.track_model.objects.select_related("asset__reciter")
            .filter(publisher_q, asset_id=asset_id)
            .order_by("surah_number")
        )
        if prefetch_timings:
            qs = qs.prefetch_related("ayah_timings")
        return qs

    def list_reciters_qs(self, publisher_q: Q, filters_dict: dict[str, Any]) -> QuerySet[Reciter]:
        """
        Returns a queryset of Reciter objects that have READY recitation assets
        for the given publisher, with optional filters applied.
        """
        recitation_filter = (
            Q(
                assets__category=Resource.CategoryChoice.RECITATION,
                assets__resource__category=Resource.CategoryChoice.RECITATION,
                assets__resource__status=Resource.StatusChoice.READY,
            )
            & publisher_q
        )

        qs = (
            Reciter.objects.filter(
                is_active=True,
            )
            .filter(recitation_filter)
            .distinct()
            .annotate(
                recitations_count=Count(
                    "assets",
                    filter=recitation_filter,
                )
            )
            .order_by("name")
        )

        # Apply filters if provided
        if filters_dict:
            if names := filters_dict.get("name__in"):
                qs = qs.filter(name__in=names)
            if names_ar := filters_dict.get("name_ar__in"):
                qs = qs.filter(name_ar__in=names_ar)
            if slugs := filters_dict.get("slug__in"):
                qs = qs.filter(slug__in=slugs)

        return qs

    def list_riwayahs_qs(self, publisher_q: Q, filters_dict: dict[str, Any]) -> QuerySet[Riwayah]:
        """
        Returns a queryset of Riwayah objects that have READY recitation assets.

        Conditions:
        - Riwayah.is_active = True
        - Asset.category = RECITATION
        - Asset.riwayah = this Riwayah
        - Asset.resource.category = RECITATION
        - Asset.resource.status = READY
        """
        recitation_filter = (
            Q(
                assets__category=Resource.CategoryChoice.RECITATION,
                assets__riwayah__isnull=False,
                assets__resource__category=Resource.CategoryChoice.RECITATION,
                assets__resource__status=Resource.StatusChoice.READY,
            )
            & publisher_q
        )

        qs = (
            self.riwayah_model.objects.filter(
                is_active=True,
            )
            .filter(recitation_filter)
            .distinct()
            .annotate(
                recitations_count=Count(
                    "assets",
                    filter=recitation_filter,
                )
            )
            .order_by("name")
            .select_related("qiraah")
        )

        # Apply filters if provided
        if filters_dict:
            # Allow explicit is_active filter (handles False correctly)
            if "is_active" in filters_dict:
                qs = qs.filter(is_active=filters_dict.get("is_active"))
            if name := filters_dict.get("name"):
                qs = qs.filter(name__icontains=name)
            if slug := filters_dict.get("slug"):
                qs = qs.filter(slug__icontains=slug)
            if qiraah_id := filters_dict.get("qiraah_id"):
                qs = qs.filter(qiraah_id=qiraah_id)

        return qs

    def list_qiraahs_qs(self, publisher_q: Q, filters_dict: dict[str, Any]) -> QuerySet[Qiraah]:
        """
        Returns a queryset of Qiraah objects that have READY recitation assets through riwayahs.

        Conditions:
        - Qiraah.is_active = True
        - Qiraah has at least one active Riwayah
        - Riwayah.is_active = True
        - Asset.category = RECITATION
        - Asset.resource.category = RECITATION
        - Asset.resource.status = READY
        """
        recitation_filter = (
            Q(
                riwayahs__assets__category=Resource.CategoryChoice.RECITATION,
                riwayahs__assets__riwayah__isnull=False,
                riwayahs__assets__resource__category=Resource.CategoryChoice.RECITATION,
                riwayahs__assets__resource__status=Resource.StatusChoice.READY,
            )
            & publisher_q
        )

        qs = (
            self.qiraah_model.objects.filter(
                riwayahs__is_active=True,
            )
            .filter(recitation_filter)
            .distinct()
            .annotate(
                riwayahs_count=Count("riwayahs", filter=Q(is_active=True), distinct=True),
                recitations_count=Count(
                    "riwayahs__assets",
                    filter=recitation_filter,
                    distinct=True,
                ),
            )
            .order_by("name")
            .prefetch_related("riwayahs")
        )

        # Apply filters if provided
        if filters_dict:
            # Allow explicit is_active filter to filter qiraahs (handles False correctly)
            if "is_active" in filters_dict:
                qs = qs.filter(is_active=filters_dict.get("is_active"))
            if name := filters_dict.get("name"):
                qs = qs.filter(name__icontains=name)
            if slug := filters_dict.get("slug"):
                qs = qs.filter(slug__icontains=slug)

        return qs

    def get_dashboard_stats(self, publisher_q: Q) -> dict[str, Any]:
        """
        Compute aggregate statistics for the recitations dashboard.
        Returns a dict with total counts and per-dimension breakdowns.
        """
        # Base filter for READY recitation assets
        base_q = Q(
            category=Resource.CategoryChoice.RECITATION,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
        ) & publisher_q

        total_recitations = self.asset_model.objects.filter(base_q).count()

        # Reciters with at least one READY recitation
        reciter_pub_q = Q(**{
            k.replace("resource__publisher", "assets__resource__publisher"): v
            for k, v in publisher_q.children
        }) if publisher_q.children else Q()

        total_reciters = (
            Reciter.objects.filter(
                is_active=True,
                assets__category=Resource.CategoryChoice.RECITATION,
                assets__resource__category=Resource.CategoryChoice.RECITATION,
                assets__resource__status=Resource.StatusChoice.READY,
            )
            .filter(reciter_pub_q)
            .distinct()
            .count()
        )

        # Track count for READY recitation assets
        track_base_q = Q(
            asset__category=Resource.CategoryChoice.RECITATION,
            asset__resource__category=Resource.CategoryChoice.RECITATION,
            asset__resource__status=Resource.StatusChoice.READY,
        )
        total_tracks = self.track_model.objects.filter(track_base_q).count()

        # Per-riwayah breakdown
        riwayah_pub_q = reciter_pub_q  # reuse the publisher Q adapted for riwayah
        per_riwayah = list(
            self.riwayah_model.objects.filter(
                is_active=True,
                assets__category=Resource.CategoryChoice.RECITATION,
                assets__resource__category=Resource.CategoryChoice.RECITATION,
                assets__resource__status=Resource.StatusChoice.READY,
            )
            .annotate(count=Count("assets", filter=base_q))
            .values("id", "name", "count")
            .order_by("-count")
        )

        # Per-type (madd_level) breakdown
        per_type = list(
            self.asset_model.objects.filter(base_q)
            .values("madd_level")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return {
            "total_reciters": total_reciters,
            "total_recitations": total_recitations,
            "total_tracks": total_tracks,
            "per_riwayah": per_riwayah,
            "per_type": per_type,
        }

    def get_reciter_by_id(self, reciter_id: int) -> Reciter | None:
        """Fetch a single active reciter by primary key."""
        try:
            return Reciter.objects.get(id=reciter_id, is_active=True)
        except Reciter.DoesNotExist:
            return None

    def list_recitations_for_reciter(
        self, reciter: Reciter, publisher_q: Q
    ):
        """
        Return recitation Assets for *reciter* with tracks prefetched.
        Only READY resources belonging to the publisher are included.
        """
        return (
            self.asset_model.objects.select_related("riwayah", "qiraah")
            .prefetch_related("recitation_tracks")
            .filter(
                publisher_q,
                reciter=reciter,
                category=Resource.CategoryChoice.RECITATION,
                resource__category=Resource.CategoryChoice.RECITATION,
                resource__status=Resource.StatusChoice.READY,
            )
            .order_by("-created_at")
        )

