from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import ProtectedError, QuerySet
from django.utils.translation import gettext as _

from apps.content.models import LicenseChoice
from apps.content.repositories.tafsir import TafsirRepository
from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher

if TYPE_CHECKING:

    from apps.content.models import Asset


class TafsirService:
    def __init__(self, repo: TafsirRepository | None = None) -> None:
        self.repo = repo or TafsirRepository()

    def get_all_tafsirs(self, filters: Any = None) -> QuerySet[Asset]:
        """
        Business Logic: Retrieve all tafsirs with optional filtering.
        """
        filters_dict = filters.model_dump(exclude_none=True) if filters and hasattr(filters, "model_dump") else {}
        return self.repo.list_tafsirs_qs(filters_dict)

    def get_tafsir(self, tafsir_slug: str) -> Asset:
        """
        Business Logic: Retrieve a single tafsir by slug.
        Raises ItqanError if not found.
        """
        tafsir = self.repo.get_tafsir(tafsir_slug)
        if tafsir is None:
            raise ItqanError(
                error_name="tafsir_not_found",
                message=_("Tafsir with slug {slug} not found.").format(slug=tafsir_slug),
                status_code=404,
            )
        return tafsir

    def create_tafsir(
        self,
        *,
        publisher_id: int,
        name_ar: str,
        name_en: str,
        description_ar: str,
        description_en: str,
        long_description_ar: str,
        long_description_en: str,
        license: LicenseChoice,
        language: str,
        is_external: bool = False,
        external_url: str | None = None,
        thumbnail_url: Any | None = None,
    ) -> Asset:
        """
        Business Logic: Create a new tafsir.
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
                error_name="tafsir_name_required",
                message=_("Tafsir name (Arabic or English) is required."),
                status_code=400,
            )

        description = description_ar or description_en

        if is_external and not external_url:
            raise ItqanError(
                error_name="external_url_required",
                message=_("External URL is required when is_external is True."),
                status_code=400,
            )
        if not is_external:
            external_url = None

        return self.repo.create_tafsir(
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
        )

    def update_tafsir(
        self,
        tafsir_slug: str,
        fields: dict[str, Any],
    ) -> Asset:
        """
        Business Logic: Update an existing tafsir.
        Validates name requirement, lets repository handle field setting and syncing.
        """
        asset = self.get_tafsir(tafsir_slug)

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
                    error_name="tafsir_name_required",
                    message=_("Tafsir name (Arabic or English) is required."),
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

        return self.repo.update_tafsir(asset, fields=fields)

    def delete_tafsir(self, tafsir_slug: str) -> None:
        """
        Business Logic: Delete a tafsir and its resource.
        """
        asset = self.get_tafsir(tafsir_slug)
        try:
            self.repo.delete_tafsir(asset)
        except ProtectedError as exc:
            raise ItqanError(
                error_name="related_objects_exist",
                message=str(_("Cannot delete Tafsir because they are referenced through other objects")),
                status_code=400,
            ) from exc
