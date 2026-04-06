from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.content.models import Asset, LicenseChoice, Resource

if TYPE_CHECKING:
    from django.db.models import QuerySet


class TranslationRepository:
    def __init__(self) -> None:
        self.asset_model = Asset
        self.resource_model = Resource

    def list_translations_qs(self, filters_dict: dict[str, Any]) -> QuerySet[Asset]:
        """
        Returns a queryset of Translation assets (category=TRANSLATION, status=READY).
        """
        qs = self.asset_model.objects.select_related("resource", "resource__publisher").filter(
            category=Resource.CategoryChoice.TRANSLATION,
            resource__category=Resource.CategoryChoice.TRANSLATION,
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

    def get_translation(self, translation_slug: str) -> Asset | None:
        """
        Get a single translation asset by slug with prefetched versions.
        """
        try:
            return (
                self.asset_model.objects.select_related("resource", "resource__publisher")
                .prefetch_related("resource__versions")
                .get(
                    slug=translation_slug,
                    category=Resource.CategoryChoice.TRANSLATION,
                    resource__category=Resource.CategoryChoice.TRANSLATION,
                )
            )
        except Asset.DoesNotExist:
            return None

    def create_translation(
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
    ) -> Asset:
        """
        Create a Resource and Asset for a new Translation.
        """
        # Create Resource first
        resource = self.resource_model.objects.create(
            publisher_id=publisher_id,
            category=Resource.CategoryChoice.TRANSLATION,
            name=name,
            description=description,
            license=license,
            status=Resource.StatusChoice.READY,
        )

        # Create Asset with localized fields
        asset = self.asset_model.objects.create(
            resource=resource,
            category=Resource.CategoryChoice.TRANSLATION,
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
            is_external=resource.is_external,
            external_url=resource.external_url,
        )

        return asset

    def update_translation(
        self,
        asset: Asset,
        fields: dict[str, Any],
    ) -> Asset:
        """
        Update translation asset fields and sync to resource.
        Properly handles modeltranslation fields by setting localized fields only
        and letting modeltranslation handle base field synchronization.
        """
        # Separate translation fields from other fields
        translation_fields = {
            "name_ar",
            "name_en",
            "description_ar",
            "description_en",
            "long_description_ar",
            "long_description_en",
        }

        # Set all non-translation fields
        for field, value in fields.items():
            if field not in translation_fields:
                setattr(asset, field, value)

        # Set translation fields (skip empty strings to avoid overriding modeltranslation values)
        for field in translation_fields:
            if field in fields:
                value = fields[field]
                if value == "":  # Skip empty translation fields
                    continue
                setattr(asset, field, value)

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

    def delete_translation(self, asset: Asset) -> None:
        """
        Delete the asset and its resource.
        """
        resource = asset.resource
        asset.delete()
        resource.delete()
