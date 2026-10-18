from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import ProtectedError, Q
from django.utils.translation import gettext as _

from apps.content.models import Asset as AssetModel, AssetVersion, CategoryChoice, LicenseChoice
from apps.content.repositories.mushaf import MushafRepository
from apps.content.services.asset_access import guard_restrict_for_tenant
from apps.content.services.asset_content import (
    AssetContentService,
    VersionBump,
    forbid_published_version_change,
    issue_version_number,
)
from apps.content.services.asset_slug import AssetSlugService
from apps.content.version_text import VersionText
from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher

logger = logging.getLogger(__name__)

if TYPE_CHECKING:

    from apps.content.models import Asset


class MushafService:
    def __init__(self, repo: MushafRepository | None = None) -> None:
        self.repo = repo or MushafRepository()

    def _get_mushaf_or_404(self, mushaf_slug: str, publisher_q: Q | None = None) -> Asset:
        try:
            qs = AssetModel.objects.all()
            if publisher_q is not None:
                qs = qs.filter(publisher_q)
            return qs.get(slug=mushaf_slug, category=CategoryChoice.MUSHAF)
        except AssetModel.DoesNotExist as exc:
            raise ItqanError(
                error_name="mushaf_not_found",
                message=_("Mushaf with slug {slug} not found.").format(slug=mushaf_slug),
                status_code=404,
            ) from exc

    def create_mushaf(
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
        slug: str | None = None,
    ) -> Asset:
        """
        Business Logic: Create a new mushaf.
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
                error_name="mushaf_name_required",
                message=_("Mushaf name (Arabic or English) is required."),
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

        # No AI here: the portal sends the slug its Translate call returned (POST /portal/ai/translate/).
        slug = AssetSlugService().resolve_slug(
            category=CategoryChoice.MUSHAF,
            requested=slug,
            name_en=normalized_name_en,
            name_ar=normalized_name_ar,
            language=language,
        )
        mushaf = self.repo.create_mushaf(
            slug=slug,
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
        logger.info(f"Mushaf created [asset_id={mushaf.pk}, publisher_id={publisher_id}, language={language}]")
        return mushaf

    def create_mushaf_with_optional_version(
        self,
        *,
        version_text: VersionText | None = None,
        version_number: str | None = None,
        file: Any = None,
        **mushaf_kwargs: Any,
    ) -> Asset:
        """
        Business Logic: Create a mushaf and, when a file is provided, its first
        version in a single atomic transaction. ``version_number`` is required
        then: it starts the mushaf's version sequence.

        ``mushaf_kwargs`` are forwarded verbatim to :meth:`create_mushaf`.
        """
        with transaction.atomic():
            mushaf = self.create_mushaf(**mushaf_kwargs)
            if file is not None:
                # The first version is the mushaf's initial content: it is published with it.
                self.create_mushaf_version(
                    mushaf.slug,
                    text=version_text,
                    version_number=version_number,
                    file=file,
                    publish=True,
                )
        mushaf.refresh_from_db()
        return mushaf

    def update_mushaf(
        self,
        mushaf_slug: str,
        fields: dict[str, Any],
        publisher_q: Q | None = None,
    ) -> Asset:
        """
        Business Logic: Update an existing mushaf.
        Validates name requirement, lets repository handle field setting and syncing.
        """
        asset = self._get_mushaf_or_404(mushaf_slug, publisher_q=publisher_q)

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
                    error_name="mushaf_name_required",
                    message=_("Mushaf name (Arabic or English) is required."),
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

        updated = self.repo.update_mushaf(asset, fields=fields)
        logger.info(f"Mushaf updated [asset_id={updated.pk}, slug={mushaf_slug}]")
        return updated

    def delete_mushaf(self, mushaf_slug: str, publisher_q: Q | None = None) -> None:
        """
        Business Logic: Delete a mushaf and its resource.
        """
        asset = self._get_mushaf_or_404(mushaf_slug, publisher_q=publisher_q)
        try:
            self.repo.delete_mushaf(asset)
            logger.info(f"Mushaf deleted [asset_id={asset.pk}, slug={mushaf_slug}]")
        except ProtectedError as exc:
            raise ItqanError(
                error_name="related_objects_exist",
                message=str(_("Cannot delete Mushaf because they are referenced through other objects")),
                status_code=400,
            ) from exc

    def _get_mushaf_version_or_404(
        self, mushaf_slug: str, version_id: int, publisher_q: Q | None = None
    ) -> AssetVersion:
        asset = self._get_mushaf_or_404(mushaf_slug, publisher_q=publisher_q)
        version = self.repo.get_mushaf_version(asset, version_id)
        if version is None:
            raise ItqanError(
                error_name="version_not_found",
                message=_("Version with id {id} not found for mushaf {slug}.").format(id=version_id, slug=mushaf_slug),
                status_code=404,
            )
        return version

    def create_mushaf_version(
        self,
        mushaf_slug: str,
        *,
        text: VersionText | None = None,
        version_number: str | None = None,
        bump: VersionBump = "minor",
        file: Any = None,
        publish: bool = False,
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """
        Business Logic: Create a new version for a mushaf.

        The version is issued the next number in the mushaf's sequence (it has one
        language): ``version_number`` starts the sequence, otherwise the latest is
        bumped by ``bump``. The package registry only serves versions whose name is
        a version number, so it is never left to the publisher to type.
        """
        asset = self._get_mushaf_or_404(mushaf_slug, publisher_q=publisher_q)
        with transaction.atomic():
            name = issue_version_number(asset, None, start=version_number, bump=bump)
            version = self.repo.create_mushaf_version(
                asset,
                name=name,
                text=text,
                file=file,
            )
        logger.info(f"Mushaf version created [version_id={version.pk}, asset_id={asset.pk}, slug={mushaf_slug}]")
        # Consumers get it (and subscribers are emailed) once it is published.
        if publish:
            version = AssetContentService().publish_new_version(asset, version)
        return version

    def update_mushaf_version(
        self,
        mushaf_slug: str,
        version_id: int,
        fields: dict[str, Any],
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """
        Business Logic: Update an existing mushaf version.
        """
        version = self._get_mushaf_version_or_404(mushaf_slug, version_id, publisher_q=publisher_q)
        if "file_url" in fields:
            forbid_published_version_change(version)
        # The version number is fixed once issued.
        fields = {key: value for key, value in fields.items() if key != "name"}
        updated = self.repo.update_mushaf_version(version, fields=fields)
        logger.info(f"Mushaf version updated [version_id={version_id}, asset_slug={mushaf_slug}]")
        return updated

    def delete_mushaf_version(self, mushaf_slug: str, version_id: int, publisher_q: Q | None = None) -> None:
        """
        Business Logic: Delete a mushaf version.
        """
        version = self._get_mushaf_version_or_404(mushaf_slug, version_id, publisher_q=publisher_q)
        forbid_published_version_change(version)
        self.repo.delete_mushaf_version(version)
        logger.info(f"Mushaf version deleted [version_id={version_id}, asset_slug={mushaf_slug}]")
