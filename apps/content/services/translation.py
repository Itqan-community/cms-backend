from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db.models import ProtectedError, Q
from django.utils.translation import gettext as _

from apps.content.models import Asset as AssetModel, AssetVersion, CategoryChoice, LicenseChoice, StatusChoice
from apps.content.repositories.translation import TranslationRepository
from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher

logger = logging.getLogger(__name__)

if TYPE_CHECKING:

    from apps.content.models import Asset


class TranslationService:
    def __init__(self, repo: TranslationRepository | None = None) -> None:
        self.repo = repo or TranslationRepository()

    def _get_translation_or_404(self, translation_slug: str, user_publisher_q: Q | None = None) -> Asset:
        try:
            qs = AssetModel.objects.all()
            if user_publisher_q is not None:
                qs = qs.filter(user_publisher_q)
            return qs.get(slug=translation_slug, category=CategoryChoice.TRANSLATION, status=StatusChoice.READY)
        except AssetModel.DoesNotExist as exc:
            raise ItqanError(
                error_name="translation_not_found",
                message=_("Translation with slug {slug} not found.").format(slug=translation_slug),
                status_code=404,
            ) from exc

    def create_translation(
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
    ) -> Asset:
        """
        Business Logic: Create a new translation.
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
                error_name="translation_name_required",
                message=_("Translation name (Arabic or English) is required."),
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

        translation = self.repo.create_translation(
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
        )
        logger.info(
            f"Translation created [asset_id={translation.pk}, publisher_id={publisher_id}, language={language}]"
        )
        return translation

    def update_translation(
        self,
        translation_slug: str,
        fields: dict[str, Any],
        user_publisher_q: Q | None = None,
    ) -> Asset:
        """
        Business Logic: Update an existing translation.
        Validates name requirement, lets repository handle field setting and syncing.
        """
        asset = self._get_translation_or_404(translation_slug, user_publisher_q=user_publisher_q)

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
                    error_name="translation_name_required",
                    message=_("Translation name (Arabic or English) is required."),
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

        updated = self.repo.update_translation(asset, fields=fields)
        logger.info(f"Translation updated [asset_id={updated.pk}, slug={translation_slug}]")
        return updated

    def delete_translation(self, translation_slug: str, user_publisher_q: Q | None = None) -> None:
        """
        Business Logic: Delete a translation and its resource.
        """
        asset = self._get_translation_or_404(translation_slug, user_publisher_q=user_publisher_q)
        try:
            self.repo.delete_translation(asset)
            logger.info(f"Translation deleted [asset_id={asset.pk}, slug={translation_slug}]")
        except ProtectedError as exc:
            raise ItqanError(
                error_name="related_objects_exist",
                message=str(_("Cannot delete Translation because they are referenced through other objects")),
                status_code=400,
            ) from exc

    def _get_translation_version_or_404(
        self, translation_slug: str, version_id: int, user_publisher_q: Q | None = None
    ) -> AssetVersion:
        asset = self._get_translation_or_404(translation_slug, user_publisher_q=user_publisher_q)
        version = self.repo.get_translation_version(asset, version_id)
        if version is None:
            raise ItqanError(
                error_name="version_not_found",
                message=_("Version with id {id} not found for translation {slug}.").format(
                    id=version_id, slug=translation_slug
                ),
                status_code=404,
            )
        return version

    def create_translation_version(
        self,
        translation_slug: str,
        *,
        name: str,
        summary: str = "",
        file: Any = None,
        user_publisher_q: Q | None = None,
    ) -> AssetVersion:
        """
        Business Logic: Create a new version for a translation.
        """
        asset = self._get_translation_or_404(translation_slug, user_publisher_q=user_publisher_q)
        version = self.repo.create_translation_version(
            asset,
            name=name,
            summary=summary,
            file=file,
        )
        logger.info(
            f"Translation version created [version_id={version.pk}, asset_id={asset.pk}, slug={translation_slug}]"
        )
        return version

    def update_translation_version(
        self,
        translation_slug: str,
        version_id: int,
        fields: dict[str, Any],
        user_publisher_q: Q | None = None,
    ) -> AssetVersion:
        """
        Business Logic: Update an existing translation version.
        """
        version = self._get_translation_version_or_404(translation_slug, version_id, user_publisher_q=user_publisher_q)
        updated = self.repo.update_translation_version(version, fields=fields)
        logger.info(f"Translation version updated [version_id={version_id}, asset_slug={translation_slug}]")
        return updated

    def delete_translation_version(
        self, translation_slug: str, version_id: int, user_publisher_q: Q | None = None
    ) -> None:
        """
        Business Logic: Delete a translation version.
        """
        version = self._get_translation_version_or_404(translation_slug, version_id, user_publisher_q=user_publisher_q)
        self.repo.delete_translation_version(version)
        logger.info(f"Translation version deleted [version_id={version_id}, asset_slug={translation_slug}]")
