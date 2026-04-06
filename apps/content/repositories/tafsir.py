from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction

from apps.content.models import Asset, LicenseChoice, Resource

if TYPE_CHECKING:
    from django.db.models import QuerySet


class TafsirRepository:
    def __init__(self) -> None:
        self.asset_model = Asset
        self.resource_model = Resource

    def list_tafsirs_qs(self, filters_dict: dict[str, Any]) -> QuerySet[Asset]:
        """
        Returns a queryset of Tafsir assets (category=TAFSIR, status=READY).
        """
        qs = self.asset_model.objects.select_related("resource", "resource__publisher").filter(
            category=Resource.CategoryChoice.TAFSIR,
            resource__category=Resource.CategoryChoice.TAFSIR,
            resource__status=Resource.StatusChoice.READY,
        )

        if filters_dict:
            if publisher_ids := filters_dict.get("publisher_id"):
                qs = qs.filter(resource__publisher_id__in=publisher_ids)
            if license_codes := filters_dict.get("license_code"):
                qs = qs.filter(license__in=license_codes)
            if language := filters_dict.get("language"):
                qs = qs.filter(language=language)
            if "is_external" in filters_dict:
                qs = qs.filter(resource__is_external=filters_dict["is_external"])

        return qs.distinct()

    def get_tafsir(self, tafsir_slug: str) -> Asset | None:
        """
        Get a single tafsir asset by slug with prefetched versions.
        """
        try:
            return (
                self.asset_model.objects.select_related("resource", "resource__publisher")
                .prefetch_related("resource__versions")
                .get(
                    slug=tafsir_slug,
                    category=Resource.CategoryChoice.TAFSIR,
                    resource__category=Resource.CategoryChoice.TAFSIR,
                )
            )
        except Asset.DoesNotExist:
            return None

    def create_tafsir(
        self,
        *,
        publisher_id: int,
        name: str,
        name_ar: str,
        name_en: str,
        description: str,
        description_ar: str,
        description_en: str,
        long_description_ar: str,
        long_description_en: str,
        license: LicenseChoice,
        language: str,
        is_external: bool = False,
        external_url: str | None = None,
    ) -> Asset:
        """
        Create a Resource and Asset for a new Tafsir.
        """
        with transaction.atomic():
            # Create Resource first
            resource = self.resource_model.objects.create(
                publisher_id=publisher_id,
                category=Resource.CategoryChoice.TAFSIR,
                name=name,
                description=description,
                license=license,
                status=Resource.StatusChoice.READY,
                is_external=is_external,
                external_url=external_url,
            )

            # Create Asset with localized fields
            asset = self.asset_model.objects.create(
                resource=resource,
                category=Resource.CategoryChoice.TAFSIR,
                name=name,
                name_ar=name_ar,
                name_en=name_en,
                description=description,
                description_ar=description_ar,
                description_en=description_en,
                long_description_ar=long_description_ar,
                long_description_en=long_description_en,
                license=license,
                language=language,
                file_size="",
                format="",
                version="",
                is_external=is_external,
                external_url=external_url,
            )

        return asset

    def update_tafsir(
        self,
        asset: Asset,
        fields: dict[str, Any],
    ) -> Asset:
        """
        Update tafsir asset fields and sync to resource.
        Properly handles modeltranslation fields by setting localized fields only
        and letting modeltranslation handle base field synchronization.
        """
        # Fields that belong on the Resource model, not Asset
        resource_only_fields = {"publisher_id"}
        # Fields that must be mirrored on both Asset and Resource
        mirrored_resource_fields = {"is_external", "external_url"}

        # Separate translation fields from other fields
        translation_fields = {
            "name_ar",
            "name_en",
            "description_ar",
            "description_en",
            "long_description_ar",
            "long_description_en",
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

            # Set translation fields; empty strings are valid when clearing optional content.
            for field in translation_fields:
                if field in fields:
                    setattr(asset, field, fields[field])

            # Update resource's name/description if asset's localized fields changed
            # NOTE: Do NOT set asset.name or asset.description directly - modeltranslation will overwrite
            # the localized fields if we do. Just update the resource fields.
            if "name_ar" in fields or "name_en" in fields:
                name_ar = getattr(asset, "name_ar", "") or ""
                name_en = getattr(asset, "name_en", "") or ""
                name = name_ar or name_en
                if name:
                    asset.resource.name = name

            if "description_ar" in fields or "description_en" in fields:
                desc_ar = getattr(asset, "description_ar", "") or ""
                desc_en = getattr(asset, "description_en", "") or ""
                desc = desc_ar or desc_en
                if desc:
                    asset.resource.description = desc

            asset.save()
            asset.resource.save()

        return asset

    def delete_tafsir(self, asset: Asset) -> None:
        """
        Delete the asset and its resource.
        """
        with transaction.atomic():
            resource = asset.resource
            asset.delete()
            resource.delete()
