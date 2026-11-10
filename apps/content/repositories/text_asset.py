from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Q

from apps.content.models import (
    Asset,
    AssetTag,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    LicenseChoice,
    MushafLayout,
    StatusChoice,
)
from apps.content.version_text import VersionText


class TextAssetRepository:
    """ORM access for text assets and their versions (read + write)."""

    def __init__(self) -> None:
        self.asset_model = Asset
        self.asset_version_model = AssetVersion

    def get_ready_asset(self, tag: str, publisher_q: Q | None = None) -> Asset | None:
        """
        First READY, ayah-template text asset (lowest id), optionally scoped by
        publisher membership.

        Feeds the public verse sampler, which reads a "surah:ayah"-keyed payload
        that only an ayah-template asset produces — a surah/word/page asset is
        never a valid sample, so it is excluded here rather than relying on the
        caller to filter it out downstream.
        """
        qs = self.asset_model.objects.select_related("publisher").filter(
            category=CategoryChoice.TEXT,
            tags__slug=tag,
            status=StatusChoice.READY,
            template=AssetTemplateChoice.AYAH,
            in_public_api=True,
        )
        if publisher_q is not None:
            qs = qs.filter(publisher_q)
        return qs.order_by("id").first()

    def get_tags(self, slugs: list[str]) -> list[AssetTag]:
        return list(AssetTag.objects.filter(slug__in=slugs))

    def create_text_asset(
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
        template: AssetTemplateChoice,
        tags: list[AssetTag],
        mushaf_layout: MushafLayout | None = None,
        is_external: bool = False,
        external_url: str | None = None,
        thumbnail_url: Any | None = None,
        is_open_access: bool = False,
        in_gallery: bool = True,
        in_public_api: bool = True,
        in_cli: bool = True,
        in_tenants: bool = True,
        status: StatusChoice = StatusChoice.READY,
        slug: str = "",
    ) -> Asset:
        """
        Create an Asset for a new Text asset.
        """
        with transaction.atomic():
            asset = self.asset_model.objects.create(
                slug=slug,
                publisher_id=publisher_id,
                status=status,
                category=CategoryChoice.TEXT,
                template=template,
                mushaf_layout=mushaf_layout,
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
                is_open_access=is_open_access,
                in_gallery=in_gallery,
                in_public_api=in_public_api,
                in_cli=in_cli,
                in_tenants=in_tenants,
            )
            asset.tags.set(tags)

        return asset

    def update_text_asset(
        self,
        asset: Asset,
        fields: dict[str, Any],
    ) -> Asset:
        """
        Update text asset fields. Handles translation fields via modeltranslation
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

        tags = fields.pop("tags", None)
        with transaction.atomic():
            for field, value in fields.items():
                if field not in translation_fields:
                    setattr(asset, field, value)

            for field in translation_fields:
                if field in fields:
                    setattr(asset, field, fields[field])

            asset.save()
            if tags is not None:
                asset.tags.set(tags)

        return asset

    def delete_text_asset(self, asset: Asset) -> None:
        """
        Delete the text asset.
        """
        asset.delete()

    def get_text_asset_version(self, asset: Asset, version_id: int) -> AssetVersion | None:
        """
        Fetch a single AssetVersion belonging to the asset.
        """
        try:
            return self.asset_version_model.objects.get(asset=asset, id=version_id)
        except self.asset_version_model.DoesNotExist:
            return None

    def create_text_asset_version(
        self,
        asset: Asset,
        *,
        name: str,
        text: VersionText | None = None,
        file: Any = None,
        created_by_id: int | None = None,
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
                **(text or VersionText()).as_fields(),
                file_url=file,
                size_bytes=size_bytes,
                created_by_id=created_by_id,
            )

            asset.file_size = asset_version.human_readable_size
            asset.save()

        return asset_version

    def update_text_asset_version(
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

    def delete_text_asset_version(self, version: AssetVersion) -> None:
        """
        Delete the AssetVersion.
        """
        version.delete()
