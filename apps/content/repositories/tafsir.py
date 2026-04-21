from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction

from apps.content.models import Asset, AssetVersion, CategoryChoice, LicenseChoice, StatusChoice

if TYPE_CHECKING:
    from django.db.models import QuerySet


class TafsirRepository:
    def __init__(self) -> None:
        self.asset_model = Asset
        self.asset_version_model = AssetVersion

    def list_tafsirs_qs(self, filters_dict: dict[str, Any]) -> QuerySet[Asset]:
        """
        Returns a queryset of Tafsir assets (category=TAFSIR, status=READY).
        """
        qs = self.asset_model.objects.select_related("publisher").filter(
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
        )

        if filters_dict:
            if publisher_ids := filters_dict.get("publisher_id"):
                qs = qs.filter(publisher_id__in=publisher_ids)
            if license_codes := filters_dict.get("license_code"):
                qs = qs.filter(license__in=license_codes)
            if language := filters_dict.get("language"):
                qs = qs.filter(language=language)
            if "is_external" in filters_dict:
                qs = qs.filter(is_external=filters_dict["is_external"])

        return qs.distinct()

    def get_tafsir(self, tafsir_slug: str) -> Asset | None:
        """
        Get a single tafsir asset by slug with prefetched versions.
        """
        try:
            return (
                self.asset_model.objects.select_related("publisher")
                .prefetch_related("versions")
                .get(
                    slug=tafsir_slug,
                    category=CategoryChoice.TAFSIR,
                )
            )
        except Asset.DoesNotExist:
            return None

    def create_tafsir(
        self,
        *,
        publisher_id: int,
        name: str,
        name_ar: str | None,
        name_en: str | None,
        description: str,
        description_ar: str | None,
        description_en: str | None,
        long_description_ar: str | None,
        long_description_en: str | None,
        license: LicenseChoice,
        language: str,
        is_external: bool = False,
        external_url: str | None = None,
        thumbnail_url: Any | None = None,
    ) -> Asset:
        """
        Create an Asset for a new Tafsir.
        """
        with transaction.atomic():
            asset = self.asset_model.objects.create(
                publisher_id=publisher_id,
                status=StatusChoice.READY,
                category=CategoryChoice.TAFSIR,
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
                is_external=is_external,
                external_url=external_url,
                thumbnail_url=thumbnail_url,
            )

        return asset

    def update_tafsir(
        self,
        asset: Asset,
        fields: dict[str, Any],
    ) -> Asset:
        """
        Update tafsir asset fields. Handles translation fields via modeltranslation
        by setting localized fields only.
        """
        translation_fields = {
            "name_ar",
            "name_en",
            "description_ar",
            "description_en",
            "long_description_ar",
            "long_description_en",
        }

        with transaction.atomic():
            for field, value in fields.items():
                if field not in translation_fields:
                    setattr(asset, field, value)

            for field in translation_fields:
                if field in fields:
                    setattr(asset, field, fields[field])

            asset.save()

        return asset

    def delete_tafsir(self, asset: Asset) -> None:
        """
        Delete the tafsir asset.
        """
        asset.delete()

    def list_tafsir_versions(self, asset: Asset):
        return AssetVersion.objects.filter(asset=asset).order_by("-created_at")

    def get_tafsir_version(self, asset: Asset, version_id: int) -> AssetVersion | None:
        """
        Fetch a single AssetVersion belonging to the asset.
        """
        try:
            return self.asset_version_model.objects.get(asset=asset, id=version_id)
        except self.asset_version_model.DoesNotExist:
            return None

    def create_tafsir_version(
        self,
        asset: Asset,
        *,
        name: str,
        summary: str = "",
        file: Any = None,
    ) -> AssetVersion:
        """
        Create an AssetVersion for the asset.
        """
        with transaction.atomic():
            size_bytes = 0
            if file:
                try:
                    size_bytes = file.size
                except Exception:
                    pass

            asset_version = self.asset_version_model.objects.create(
                asset=asset,
                name=name,
                summary=summary,
                file_url=file,
                size_bytes=size_bytes,
            )

        return asset_version

    def update_tafsir_version(
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

            if "file_url" in fields and fields["file_url"]:
                file = fields["file_url"]
                try:
                    version.size_bytes = file.size
                except Exception:
                    pass

            version.save()

        return version

    def delete_tafsir_version(self, version: AssetVersion) -> None:
        """
        Delete the AssetVersion.
        """
        version.delete()
