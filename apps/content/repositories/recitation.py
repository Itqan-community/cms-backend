from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models, transaction
from django.db.models import Count, Q

from apps.content.models import (
    Asset,
    CategoryChoice,
    LicenseChoice,
    Qiraah,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
    StatusChoice,
)
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
        self, publisher_q: Q | None, filters_dict: dict[str, Any], annotate_surahs_count: bool = False
    ) -> QuerySet[Asset]:
        """
        Returns a queryset of Asset objects.
        """
        qs = self.asset_model.objects.select_related("publisher", "reciter", "riwayah", "qiraah").filter(
            category=CategoryChoice.RECITATION,
            status=StatusChoice.READY,
        )

        if publisher_q is not None:
            qs = qs.filter(publisher_q)

        if filters_dict:
            if ids := filters_dict.get("id"):
                qs = qs.filter(id__in=ids)
            if reciter_ids := filters_dict.get("reciter_id"):
                qs = qs.filter(reciter_id__in=reciter_ids)
            if riwayah_ids := filters_dict.get("riwayah_id"):
                qs = qs.filter(
                    Q(riwayah_id__in=riwayah_ids)
                    # get recitations with combined riwayahs under one qiraah, but no single riwayah
                    | Q(riwayah__isnull=True, qiraah__in=Riwayah.objects.filter(id__in=riwayah_ids).values("qiraah_id"))
                )
            if qiraah_ids := filters_dict.get("qiraah_id"):
                qs = qs.filter(qiraah_id__in=qiraah_ids)
            if publisher_ids := filters_dict.get("publisher_id"):
                qs = qs.filter(publisher_id__in=publisher_ids)
            if madd_levels := filters_dict.get("madd_level"):
                qs = qs.filter(madd_level__in=madd_levels)
            if meem_behaviours := filters_dict.get("meem_behaviour"):
                qs = qs.filter(meem_behaviour__in=meem_behaviours)
            if year := filters_dict.get("year"):
                qs = qs.filter(year=year)
            if license_codes := filters_dict.get("license_code"):
                qs = qs.filter(license__in=license_codes)

        if annotate_surahs_count:
            qs = qs.annotate(surahs_count=Count("recitation_tracks"))

        # Sorting support
        qs = qs.annotate(
            reciter_name=models.F("reciter__name"),
            qiraah_name=models.F("qiraah__name"),
            riwayah_name=models.F("riwayah__name"),
        )

        return qs.distinct()

    def get_recitation(self, recitation_slug: str) -> Asset | None:
        """
        Get a single recitation asset by slug.
        """
        try:
            return (
                self.asset_model.objects.select_related("publisher", "reciter", "riwayah", "qiraah")
                .prefetch_related("versions")
                .get(
                    slug=recitation_slug,
                    category=CategoryChoice.RECITATION,
                )
            )
        except Asset.DoesNotExist:
            return None

    def create_recitation(
        self,
        *,
        publisher_id: int,
        name: str,
        name_ar: str | None = None,
        name_en: str | None = None,
        description: str,
        description_ar: str | None = None,
        description_en: str | None = None,
        license: LicenseChoice,
        reciter_id: int,
        qiraah_id: int | None,
        riwayah_id: int | None,
        madd_level: Asset.MaddLevelChoice | None,
        meem_behaviour: Asset.MeemBehaviourChoice | None,
        year: int | None,
    ) -> Asset:
        """
        Create an Asset for a new Recitation.
        """
        with transaction.atomic():
            asset = self.asset_model.objects.create(
                publisher_id=publisher_id,
                status=StatusChoice.READY,
                category=CategoryChoice.RECITATION,
                name=name,
                name_ar=name_ar,
                name_en=name_en,
                description=description,
                description_ar=description_ar,
                description_en=description_en,
                license=license,
                language="ar",  # Default for recitations?
                file_size="",
                format="",
                reciter_id=reciter_id,
                qiraah_id=qiraah_id,
                riwayah_id=riwayah_id,
                madd_level=madd_level,
                meem_behaviour=meem_behaviour,
                year=year,
            )

        return asset

    def update_recitation(
        self,
        asset: Asset,
        fields: dict[str, Any],
    ) -> Asset:
        """
        Update recitation asset fields.
        """
        translation_fields = {
            "name_ar",
            "name_en",
            "description_ar",
            "description_en",
        }

        with transaction.atomic():
            for field, value in fields.items():
                if field not in translation_fields:
                    setattr(asset, field, value)
                else:
                    setattr(asset, field, (value or "").strip())

            # Mirror localized fields into the unlocalized name/description
            if any(f in fields for f in ["name_ar", "name_en"]):
                name_ar = getattr(asset, "name_ar", "") or ""
                name_en = getattr(asset, "name_en", "") or ""
                asset.name = name_ar or name_en

            if any(f in fields for f in ["description_ar", "description_en"]):
                desc_ar = getattr(asset, "description_ar", "") or ""
                desc_en = getattr(asset, "description_en", "") or ""
                asset.description = desc_ar or desc_en

            asset.save()

        return asset

    def delete_recitation(self, asset: Asset) -> None:
        """
        Delete the recitation asset.
        """
        asset.delete()

    def get_recitation_asset(self, asset_id: int, publisher_q: Q | None) -> dict[str, Any] | None:
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

    def get_asset_object(self, asset_id: int, publisher_q: Q | None) -> Asset | None:
        """Utility for internal use within the service if needed"""
        try:
            query = Q(
                id=asset_id,
                category=CategoryChoice.RECITATION,
                status=StatusChoice.READY,
            )
            if publisher_q is not None:
                query &= publisher_q
            return self.asset_model.objects.select_related("publisher").get(query)
        except Asset.DoesNotExist:
            return None

    def list_recitation_tracks_for_asset(
        self, asset_id: int, publisher_q: Q | None, prefetch_timings: bool = False
    ) -> QuerySet[RecitationSurahTrack]:
        query = Q(asset_id=asset_id)
        if publisher_q is not None:
            query &= publisher_q

        qs = self.track_model.objects.select_related("asset__reciter").filter(query).order_by("surah_number")
        if prefetch_timings:
            qs = qs.prefetch_related("ayah_timings")
        return qs

    def list_reciters_qs(self, publisher_q: Q | None, filters_dict: dict[str, Any]) -> QuerySet[Reciter]:
        """
        Returns a queryset of Reciter objects that have READY recitation assets
        for the given publisher, with optional filters applied.
        """
        recitation_filter = Q(
            assets__category=CategoryChoice.RECITATION,
            assets__status=StatusChoice.READY,
        )
        if publisher_q is not None:
            recitation_filter &= publisher_q

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

    def list_riwayahs_qs(self, publisher_q: Q | None, filters_dict: dict[str, Any]) -> QuerySet[Riwayah]:
        """
        Returns a queryset of Riwayah objects that have READY recitation assets.
        """
        recitation_filter = Q(
            assets__category=CategoryChoice.RECITATION,
            assets__riwayah__isnull=False,
            assets__status=StatusChoice.READY,
        )
        if publisher_q is not None:
            recitation_filter &= publisher_q

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

        if filters_dict:
            if "is_active" in filters_dict:
                qs = qs.filter(is_active=filters_dict.get("is_active"))
            if name := filters_dict.get("name"):
                qs = qs.filter(name__icontains=name)
            if slug := filters_dict.get("slug"):
                qs = qs.filter(slug__icontains=slug)
            if qiraah_id := filters_dict.get("qiraah_id"):
                qs = qs.filter(qiraah_id=qiraah_id)

        return qs

    def list_qiraahs_qs(self, publisher_q: Q | None, filters_dict: dict[str, Any]) -> QuerySet[Qiraah]:
        """
        Returns a queryset of Qiraah objects that have READY recitation assets through riwayahs.
        """
        recitation_filter = Q(
            riwayahs__assets__category=CategoryChoice.RECITATION,
            riwayahs__assets__riwayah__isnull=False,
            riwayahs__assets__status=StatusChoice.READY,
        )
        if publisher_q is not None:
            recitation_filter &= publisher_q

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

        if filters_dict:
            if "is_active" in filters_dict:
                qs = qs.filter(is_active=filters_dict.get("is_active"))
            if name := filters_dict.get("name"):
                qs = qs.filter(name__icontains=name)
            if slug := filters_dict.get("slug"):
                qs = qs.filter(slug__icontains=slug)

        return qs
