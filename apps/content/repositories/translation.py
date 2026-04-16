from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction

from apps.content.models import Asset, AssetVersion, LicenseChoice, Resource, ResourceVersion

if TYPE_CHECKING:
    from django.db.models import QuerySet


class TranslationRepository:
    def __init__(self) -> None:
        self.asset_model = Asset
        self.resource_model = Resource
        self.asset_version_model = AssetVersion
        self.resource_version_model = ResourceVersion

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
                    resource__status=Resource.StatusChoice.READY,
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
        is_external: bool = False,
        external_url: str | None = None,
    ) -> Asset:
        """
        Create a Resource and Asset for a new Translation.
        """
        with transaction.atomic():
            # Create Resource first
            resource = self.resource_model.objects.create(
                publisher_id=publisher_id,
                category=Resource.CategoryChoice.TRANSLATION,
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
                is_external=is_external,
                external_url=external_url,
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
            # Set all non-translation fields
            for field, value in fields.items():
                if field in resource_only_fields:
                    setattr(asset.resource, field, value)
                elif field in mirrored_resource_fields:
                    setattr(asset, field, value)
                    setattr(asset.resource, field, value)
                elif field not in translation_fields:
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
        with transaction.atomic():
            resource = asset.resource
            asset.delete()
            resource.delete()

    def list_translation_versions(self, asset: Asset):
        return AssetVersion.objects.filter(asset=asset).order_by("-created_at")

    def get_translation_version(self, asset: Asset, version_id: int) -> AssetVersion | None:
        """
        Fetch a single AssetVersion belonging to the asset.
        """
        try:
            return self.asset_version_model.objects.get(asset=asset, id=version_id)
        except self.asset_version_model.DoesNotExist:
            return None

    def create_translation_version(
        self,
        asset: Asset,
        *,
        name: str,
        summary: str = "",
        file: Any = None,
    ) -> AssetVersion:
        """
        Atomically creates a ResourceVersion and its corresponding AssetVersion.
        Automatically handles semvar generation.
        """
        with transaction.atomic():
            # Generate sequential semvar based on existing resource versions
            last_version = asset.resource.versions.order_by("-created_at").first()
            if last_version:
                try:
                    # Simple increment of major version for now: X.0.0
                    major = int(last_version.semvar.split(".")[0])
                    new_semvar = f"{major + 1}.0.0"
                except (ValueError, IndexError):
                    new_semvar = "1.0.0"
            else:
                new_semvar = "1.0.0"

            # Create the ResourceVersion
            resource_version = self.resource_version_model.objects.create(
                resource=asset.resource,
                name=name,
                summary=summary,
                semvar=new_semvar,
            )

            # Create the AssetVersion
            asset_version = self.asset_version_model.objects.create(
                asset=asset,
                resource_version=resource_version,
                name=name,
                summary=summary,
                file_url=file,
            )

            # File size is auto-calculated in AssetVersion.save() if not provided
            # but we can force it if needed. The model handle it.

        return asset_version

    def update_translation_version(
        self,
        version: AssetVersion,
        fields: dict[str, Any],
    ) -> AssetVersion:
        """
        Update AssetVersion fields.
        """
        with transaction.atomic():
            for field, value in fields.items():
                setattr(version, field, value)

            # If name or summary changed, we might want to sync back to resource_version
            if "name" in fields:
                version.resource_version.name = fields["name"]
            if "summary" in fields:
                version.resource_version.summary = fields["summary"]

            version.save()
            version.resource_version.save()

        return version

    def delete_translation_version(self, version: AssetVersion) -> None:
        """
        Delete the AssetVersion and its linked ResourceVersion.
        """
        with transaction.atomic():
            resource_version = version.resource_version
            version.delete()
            resource_version.delete()
