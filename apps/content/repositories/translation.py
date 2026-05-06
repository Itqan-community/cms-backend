from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.content.models import Asset, AssetVersion, CategoryChoice, LicenseChoice, StatusChoice


class TranslationRepository:
    def __init__(self) -> None:
        self.asset_model = Asset
        self.asset_version_model = AssetVersion

    def create_translation(
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
    ) -> Asset:
        """
        Create an Asset for a new Translation.
        """
        with transaction.atomic():
            asset = self.asset_model.objects.create(
                publisher_id=publisher_id,
                status=StatusChoice.READY,
                category=CategoryChoice.TRANSLATION,
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
            )

        return asset

    def update_translation(
        self,
        asset: Asset,
        fields: dict[str, Any],
    ) -> Asset:
        """
        Update translation asset fields.
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
                    value = fields[field]
                    if value == "":
                        continue
                    setattr(asset, field, value)

            asset.save()

        return asset

    def delete_translation(self, asset: Asset) -> None:
        """
        Delete the translation asset.
        """
        asset.delete()

    def get_translation_version(self, asset: Asset, version_id: int) -> AssetVersion | None:
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
        Create an AssetVersion and sync derived fields back to Asset.
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

            asset.file_size = asset_version.human_readable_size
            asset.save()

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

            new_format = None
            if "file_url" in fields and fields["file_url"]:
                file = fields["file_url"]
                try:
                    version.size_bytes = file.size
                except Exception:
                    pass
                try:
                    new_format = file.name.rsplit(".", 1)[-1].lower()
                except Exception:
                    pass

            version.save()

            if "file_url" in fields:
                version.asset.file_size = version.human_readable_size
                if new_format is not None:
                    version.asset.format = new_format
                version.asset.save()

        return version

    def delete_translation_version(self, version: AssetVersion) -> None:
        """
        Delete the AssetVersion.
        """
        version.delete()
