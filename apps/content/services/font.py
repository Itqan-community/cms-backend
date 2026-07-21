from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import ProtectedError, Q
from django.utils.translation import gettext as _

from apps.content.models import Asset as AssetModel, AssetVersion, CategoryChoice, LicenseChoice
from apps.content.repositories.font import FontRepository
from apps.content.services.asset_access import guard_restrict_for_tenant
from apps.content.tasks import notify_asset_version_created
from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher

logger = logging.getLogger(__name__)

if TYPE_CHECKING:

    from apps.content.models import Asset


class FontService:
    def __init__(self, repo: FontRepository | None = None) -> None:
        self.repo = repo or FontRepository()

    def _get_font_or_404(self, font_slug: str, publisher_q: Q | None = None) -> Asset:
        try:
            qs = AssetModel.objects.all()
            if publisher_q is not None:
                qs = qs.filter(publisher_q)
            return qs.get(slug=font_slug, category=CategoryChoice.FONT)
        except AssetModel.DoesNotExist as exc:
            raise ItqanError(
                error_name="font_not_found",
                message=_("Font with slug {slug} not found.").format(slug=font_slug),
                status_code=404,
            ) from exc

    def create_font(
        self,
        *,
        publisher_id: int,
        name_ar: str | None,
        name_en: str | None,
        description_ar: str | None,
        description_en: str | None,
        long_description_ar: str | None,
        long_description_en: str | None,
        license: LicenseChoice,
        language: str,
        is_external: bool = False,
        external_url: str | None = None,
        thumbnail_url: Any | None = None,
        is_open_access: bool = False,
        restricted_for_tenant: bool = False,
    ) -> Asset:
        """
        Business Logic: Create a new font.
        Validates publisher exists and computes base name/description.
        """
        # Validate publisher exists
        if not Publisher.objects.filter(id=publisher_id).exists():
            raise ItqanError(
                error_name="publisher_not_found",
                message=_("Publisher with id {id} not found.").format(id=publisher_id),
                status_code=404,
            )

        # Compute base name and description from localized fields
        normalized_name_ar = (name_ar or "").strip()
        normalized_name_en = (name_en or "").strip()
        name = normalized_name_ar or normalized_name_en
        if not name:
            raise ItqanError(
                error_name="font_name_required",
                message=_("Font name (Arabic or English) is required."),
                status_code=400,
            )

        description = description_ar or description_en or ""

        if is_external and not external_url:
            raise ItqanError(
                error_name="external_url_required",
                message=_("External URL is required when is_external is True."),
                status_code=400,
            )
        if not is_external:
            external_url = None

        font = self.repo.create_font(
            publisher_id=publisher_id,
            name=name,
            name_ar=normalized_name_ar,
            name_en=normalized_name_en,
            description=description,
            description_ar=description_ar,
            description_en=description_en,
            long_description_ar=long_description_ar,
            long_description_en=long_description_en,
            license=license,
            language=language,
            is_external=is_external,
            external_url=external_url,
            thumbnail_url=thumbnail_url,
            is_open_access=is_open_access,
            restricted_for_tenant=restricted_for_tenant,
        )
        logger.info(f"Font created [asset_id={font.pk}, publisher_id={publisher_id}, language={language}]")
        return font

    def create_font_with_optional_version(
        self,
        *,
        version_name: str | None = None,
        version_summary: str = "",
        file: Any = None,
        **font_kwargs: Any,
    ) -> Asset:
        """
        Business Logic: Create a font and, when a file is provided, its first
        version in a single atomic transaction.

        ``font_kwargs`` are forwarded verbatim to :meth:`create_font`.
        """
        if file is not None and not (version_name or "").strip():
            raise ItqanError(
                error_name="version_name_required",
                message=_("Version name is required when a file is provided."),
                status_code=400,
            )

        with transaction.atomic():
            font = self.create_font(**font_kwargs)
            if file is not None:
                self.create_font_version(
                    font.slug,
                    name=version_name or "",
                    summary=version_summary,
                    file=file,
                )
        font.refresh_from_db()
        return font

    def update_font(
        self,
        font_slug: str,
        fields: dict[str, Any],
        publisher_q: Q | None = None,
    ) -> Asset:
        """
        Business Logic: Update an existing font.
        Validates name requirement, lets repository handle field setting and syncing.
        """
        asset = self._get_font_or_404(font_slug, publisher_q=publisher_q)

        if fields.get("restricted_for_tenant") and not asset.restricted_for_tenant:
            guard_restrict_for_tenant(asset)

        # Validate name fields if user is trying to update them
        if "name_ar" in fields or "name_en" in fields:
            # Use new values if provided, fall back to current values
            new_name_ar = fields.get("name_ar") if "name_ar" in fields else getattr(asset, "name_ar", "")
            new_name_en = fields.get("name_en") if "name_en" in fields else getattr(asset, "name_en", "")

            # Check if at least one name field is non-empty
            final_name_ar = (new_name_ar or "").strip()
            final_name_en = (new_name_en or "").strip()

            if not final_name_ar and not final_name_en:
                raise ItqanError(
                    error_name="font_name_required",
                    message=_("Font name (Arabic or English) is required."),
                    status_code=400,
                )

        # Enforce external url rules
        is_external = fields.get("is_external", asset.is_external)
        if is_external:
            external_url = fields.get("external_url", asset.external_url)
            if not external_url:
                raise ItqanError(
                    error_name="external_url_required",
                    message=_("External URL is required when is_external is True."),
                    status_code=400,
                )
            fields["external_url"] = external_url
        else:
            fields["is_external"] = False
            fields["external_url"] = None

        updated = self.repo.update_font(asset, fields=fields)
        logger.info(f"Font updated [asset_id={updated.pk}, slug={font_slug}]")
        return updated

    def delete_font(self, font_slug: str, publisher_q: Q | None = None) -> None:
        """
        Business Logic: Delete a font and its resource.
        """
        asset = self._get_font_or_404(font_slug, publisher_q=publisher_q)
        try:
            self.repo.delete_font(asset)
            logger.info(f"Font deleted [asset_id={asset.pk}, slug={font_slug}]")
        except ProtectedError as exc:
            raise ItqanError(
                error_name="related_objects_exist",
                message=str(_("Cannot delete Font because they are referenced through other objects")),
                status_code=400,
            ) from exc

    def _get_font_version_or_404(self, font_slug: str, version_id: int, publisher_q: Q | None = None) -> AssetVersion:
        asset = self._get_font_or_404(font_slug, publisher_q=publisher_q)
        version = self.repo.get_font_version(asset, version_id)
        if version is None:
            raise ItqanError(
                error_name="version_not_found",
                message=_("Version with id {id} not found for font {slug}.").format(id=version_id, slug=font_slug),
                status_code=404,
            )
        return version

    def create_font_version(
        self,
        font_slug: str,
        *,
        name: str,
        summary: str = "",
        file: Any = None,
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """
        Business Logic: Create a new version for a font.
        """
        asset = self._get_font_or_404(font_slug, publisher_q=publisher_q)
        version = self.repo.create_font_version(
            asset,
            name=name,
            summary=summary,
            file=file,
        )
        logger.info(f"Font version created [version_id={version.pk}, asset_id={asset.pk}, slug={font_slug}]")
        notify_asset_version_created.delay(version.pk)
        return version

    def update_font_version(
        self,
        font_slug: str,
        version_id: int,
        fields: dict[str, Any],
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """
        Business Logic: Update an existing font version.
        """
        version = self._get_font_version_or_404(font_slug, version_id, publisher_q=publisher_q)
        updated = self.repo.update_font_version(version, fields=fields)
        logger.info(f"Font version updated [version_id={version_id}, asset_slug={font_slug}]")
        return updated

    def delete_font_version(self, font_slug: str, version_id: int, publisher_q: Q | None = None) -> None:
        """
        Business Logic: Delete a font version.
        """
        version = self._get_font_version_or_404(font_slug, version_id, publisher_q=publisher_q)
        self.repo.delete_font_version(version)
        logger.info(f"Font version deleted [version_id={version_id}, asset_slug={font_slug}]")
