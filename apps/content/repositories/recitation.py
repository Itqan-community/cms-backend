from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models, transaction
from django.db.models import Count, Q

from apps.content.models import Asset, LicenseChoice, Qiraah, RecitationSurahTrack, Reciter, Resource, Riwayah
from apps.content.repositories.base import BaseRecitationRepository

if TYPE_CHECKING:
    from django.db.models import QuerySet


class RecitationRepository(BaseRecitationRepository):
    def __init__(self) -> None:
        self.asset_model = Asset
        self.resource_model = Resource
        self.track_model = RecitationSurahTrack
        self.riwayah_model = Riwayah
        self.qiraah_model = Qiraah

    def list_recitations_qs(
        self, publisher_q: Q | None, filters_dict: dict[str, Any], annotate_surahs_count: bool = False
    ) -> QuerySet[Asset]:
        """
        Returns a queryset of Asset objects.
        """
        qs = self.asset_model.objects.select_related(
            "resource", "resource__publisher", "reciter", "riwayah", "qiraah"
        ).filter(
            category=Resource.CategoryChoice.RECITATION,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
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
                qs = qs.filter(resource__publisher_id__in=publisher_ids)
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
                self.asset_model.objects.select_related(
                    "resource", "resource__publisher", "reciter", "riwayah", "qiraah"
                )
                .prefetch_related("resource__versions")
                .get(
                    slug=recitation_slug,
                    category=Resource.CategoryChoice.RECITATION,
                    resource__category=Resource.CategoryChoice.RECITATION,
                )
            )
        except Asset.DoesNotExist:
            return None

    def create_recitation(
        self,
        *,
        publisher_id: int,
        name: str,
        name_ar: str,
        name_en: str,
        description: str,
        description_ar: str,
        description_en: str,
        license: LicenseChoice,
        reciter_id: int,
        qiraah_id: int,
        riwayah_id: int,
        madd_level: Asset.MaddLevelChoice | None,
        meem_behaviour: Asset.MeemBehaviourChoice | None,
        year: int,
    ) -> Asset:
        """
        Create a Resource and Asset for a new Recitation.
        """
        with transaction.atomic():
            # Create Resource first
            resource = self.resource_model.objects.create(
                publisher_id=publisher_id,
                category=Resource.CategoryChoice.RECITATION,
                name=name,
                description=description,
                license=license,
                status=Resource.StatusChoice.READY,
            )

            # Create Asset with localized fields and recitation specific fields
            asset = self.asset_model.objects.create(
                resource=resource,
                category=Resource.CategoryChoice.RECITATION,
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
                version="",
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
        Update recitation asset fields and sync to resource.
        """
        # Fields that belong on the Resource model, not Asset
        resource_only_fields = {"publisher_id"}
        # Fields that must be mirrored on both Asset and Resource
        mirrored_resource_fields = {"license"}

        # Separate translation fields from other fields
        translation_fields = {
            "name_ar",
            "name_en",
            "description_ar",
            "description_en",
        }

        with transaction.atomic():
            # Set all non-translation fields, routing to the correct model
            for field, value in fields.items():
                if field in resource_only_fields:
                    setattr(asset.resource, field, value)
                elif field in mirrored_resource_fields:
                    setattr(asset, field, value)
                    setattr(asset.resource, field, value)
                elif field not in translation_fields:
                    setattr(asset, field, value)
                else:  # translation fields
                    setattr(asset, field, (value or "").strip())

            # Update mirrored name/description on both Asset and Resource if localized fields changed
            if any(f in fields for f in ["name_ar", "name_en"]):
                name_ar = getattr(asset, "name_ar", "") or ""
                name_en = getattr(asset, "name_en", "") or ""
                name = name_ar or name_en
                asset.name = name
                asset.resource.name = name

            if any(f in fields for f in ["description_ar", "description_en"]):
                desc_ar = getattr(asset, "description_ar", "") or ""
                desc_en = getattr(asset, "description_en", "") or ""
                desc = desc_ar or desc_en
                asset.description = desc
                asset.resource.description = desc

            asset.save()
            asset.resource.save()

        return asset

    def delete_recitation(self, asset: Asset) -> None:
        """
        Delete the asset and its resource if no other assets are referencing it.
        """
        with transaction.atomic():
            resource = asset.resource
            asset.delete()
            # Only delete the resource if no other assets are referencing it
            # (Asset.resource uses on_delete=models.PROTECT)
            if not resource.assets.exists():
                resource.delete()

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
                category=Resource.CategoryChoice.RECITATION,
                resource__category=Resource.CategoryChoice.RECITATION,
                resource__status=Resource.StatusChoice.READY,
            )
            if publisher_q is not None:
                query &= publisher_q
            return self.asset_model.objects.select_related("resource", "resource__publisher").get(query)
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
            assets__category=Resource.CategoryChoice.RECITATION,
            assets__resource__category=Resource.CategoryChoice.RECITATION,
            assets__resource__status=Resource.StatusChoice.READY,
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

        Conditions:
        - Riwayah.is_active = True
        - Asset.category = RECITATION
        - Asset.riwayah = this Riwayah
        - Asset.resource.category = RECITATION
        - Asset.resource.status = READY
        """
        recitation_filter = Q(
            assets__category=Resource.CategoryChoice.RECITATION,
            assets__riwayah__isnull=False,
            assets__resource__category=Resource.CategoryChoice.RECITATION,
            assets__resource__status=Resource.StatusChoice.READY,
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

    def list_qiraahs_qs(self, publisher_q: Q | None, filters_dict: dict[str, Any]) -> QuerySet[Qiraah]:
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
        recitation_filter = Q(
            riwayahs__assets__category=Resource.CategoryChoice.RECITATION,
            riwayahs__assets__riwayah__isnull=False,
            riwayahs__assets__resource__category=Resource.CategoryChoice.RECITATION,
            riwayahs__assets__resource__status=Resource.StatusChoice.READY,
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
