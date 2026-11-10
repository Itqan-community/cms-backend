from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import ProtectedError, Q
from django.utils.translation import gettext as _

from apps.content.models import (
    GROUP_TEMPLATES,
    TAG_TAFSIR,
    Asset as AssetModel,
    AssetTag,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    LicenseChoice,
    MushafLayout,
    StatusChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.repositories.asset_review import AssetReviewRepository
from apps.content.repositories.text_asset import TextAssetRepository
from apps.content.services.asset_access import guard_channel_changes
from apps.content.services.asset_content import (
    VersionBump,
    adopt_current_columns,
    forbid_minor_after_column_reorder,
    import_uploaded_file_into_entries,
    issue_version_number,
    lock_version_for_content_change,
    lock_version_for_delete,
    set_version_language,
)
from apps.content.services.asset_slug import AssetSlugService
from apps.content.services.mushaf_layout import MushafLayoutService
from apps.content.version_text import VersionText
from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from apps.content.models import Asset
    from apps.users.models import User


class TextAssetService:
    def __init__(self, repo: TextAssetRepository | None = None) -> None:
        self.repo = repo or TextAssetRepository()

    def _get_text_asset_or_404(self, text_asset_slug: str, publisher_q: Q | None = None) -> Asset:
        try:
            qs = AssetModel.objects.all()
            if publisher_q is not None:
                qs = qs.filter(publisher_q)
            return qs.get(slug=text_asset_slug, category=CategoryChoice.TEXT)
        except AssetModel.DoesNotExist as exc:
            raise ItqanError(
                error_name="text_asset_not_found",
                message=_("Text asset with slug {slug} not found.").format(slug=text_asset_slug),
                status_code=404,
            ) from exc

    def _resolve_layout(self, template: str, mushaf_layout_id: int | None) -> MushafLayout | None:
        """Validate the template/layout pairing and resolve the layout."""
        if template == AssetTemplateChoice.PAGE:
            if mushaf_layout_id is None:
                raise ItqanError(
                    error_name="mushaf_layout_required",
                    message=_("A page-based asset requires a mushaf layout."),
                    status_code=400,
                )
            return MushafLayoutService().get_or_404(mushaf_layout_id)
        if mushaf_layout_id is not None:
            raise ItqanError(
                error_name="mushaf_layout_not_allowed",
                message=_("Only page-based assets can have a mushaf layout."),
                status_code=400,
            )
        return None

    def _resolve_tags(self, slugs: list[str]) -> list[AssetTag]:
        """The requested tags, in the order given: the first one prefixes the package name."""
        unique = list(dict.fromkeys(slugs))
        if not unique:
            raise ItqanError(
                error_name="text_asset_tag_required",
                message=_("Choose at least one tag for the text asset."),
                status_code=400,
            )
        found = {tag.slug: tag for tag in self.repo.get_tags(unique)}
        missing = [slug for slug in unique if slug not in found]
        if missing:
            raise ItqanError(
                error_name="asset_tag_not_found",
                message=_("Unknown tag: {slug}.").format(slug=missing[0]),
                status_code=400,
            )
        return [found[slug] for slug in unique]

    @staticmethod
    def _guard_group_template(template: str | None, tags: list[AssetTag]) -> None:
        """Ayah-group and word-group templates are only for tafsirs, also after a tag change."""
        if template in GROUP_TEMPLATES and not any(tag.slug == TAG_TAFSIR for tag in tags):
            raise ItqanError(
                error_name="template_not_allowed",
                message=_("Ayah-group and word-group templates are only available for assets tagged tafsir."),
                status_code=400,
            )

    def create_text_asset(
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
        template: AssetTemplateChoice,
        tags: list[str],
        mushaf_layout_id: int | None = None,
        is_external: bool = False,
        external_url: str | None = None,
        thumbnail_url: Any | None = None,
        is_open_access: bool = False,
        in_gallery: bool = True,
        in_public_api: bool = True,
        in_cli: bool = True,
        in_tenants: bool = True,
        status: StatusChoice = StatusChoice.READY,
        slug: str | None = None,
    ) -> Asset:
        """
        Business Logic: Create a new text asset.
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
                error_name="text_asset_name_required",
                message=_("Text asset name (Arabic or English) is required."),
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

        resolved_tags = self._resolve_tags(tags)
        self._guard_group_template(template, resolved_tags)
        layout = self._resolve_layout(template, mushaf_layout_id)

        # No AI here: the portal sends the slug its Translate call returned (POST /portal/ai/translate/).
        slug = AssetSlugService().resolve_slug(
            category=CategoryChoice.TEXT,
            prefix=resolved_tags[0].slug,
            requested=slug,
            name_en=normalized_name_en,
            name_ar=normalized_name_ar,
            language=language,
        )
        text_asset = self.repo.create_text_asset(
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
            template=template,
            tags=resolved_tags,
            mushaf_layout=layout,
            is_external=is_external,
            external_url=external_url,
            thumbnail_url=thumbnail_url,
            is_open_access=is_open_access,
            in_gallery=in_gallery,
            in_public_api=in_public_api,
            in_cli=in_cli,
            in_tenants=in_tenants,
            status=status,
        )
        logger.info(f"Text asset created [asset_id={text_asset.pk}, publisher_id={publisher_id}, language={language}]")
        return text_asset

    def create_text_asset_with_optional_version(
        self,
        *,
        version_text: VersionText | None = None,
        version_number: str | None = None,
        file: Any = None,
        created_by_id: int | None = None,
        **text_asset_kwargs: Any,
    ) -> Asset:
        """
        Business Logic: Create a text asset and, when a file is provided, its first
        version in a single atomic transaction.

        ``text_asset_kwargs`` are forwarded verbatim to :meth:`create_text_asset`.
        """
        with transaction.atomic():
            text_asset = self.create_text_asset(**text_asset_kwargs)
            if file is not None:
                self.create_text_asset_version(
                    text_asset.slug,
                    text=version_text,
                    version_number=version_number,
                    file=file,
                    created_by_id=created_by_id,
                )
        text_asset.refresh_from_db()
        return text_asset

    def update_text_asset(
        self,
        text_asset_slug: str,
        fields: dict[str, Any],
        publisher_q: Q | None = None,
    ) -> Asset:
        """
        Business Logic: Update an existing text asset.
        Validates name requirement, lets repository handle field setting and syncing.
        """
        asset = self._get_text_asset_or_404(text_asset_slug, publisher_q=publisher_q)

        if "template" in fields or "mushaf_layout_id" in fields:
            raise ItqanError(
                error_name="asset_template_immutable",
                message=_("An asset's template cannot be changed after creation."),
                status_code=400,
            )

        guard_channel_changes(asset, fields)

        if fields.get("tags") is None:
            fields.pop("tags", None)
        else:
            fields["tags"] = self._resolve_tags(fields["tags"])
            self._guard_group_template(asset.template, fields["tags"])

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
                    error_name="text_asset_name_required",
                    message=_("Text asset name (Arabic or English) is required."),
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

        updated = self.repo.update_text_asset(asset, fields=fields)
        logger.info(f"Text asset updated [asset_id={updated.pk}, slug={text_asset_slug}]")
        return updated

    def delete_text_asset(self, text_asset_slug: str, publisher_q: Q | None = None) -> None:
        """
        Business Logic: Delete a text asset and its resource.
        """
        asset = self._get_text_asset_or_404(text_asset_slug, publisher_q=publisher_q)
        try:
            self.repo.delete_text_asset(asset)
            logger.info(f"Text asset deleted [asset_id={asset.pk}, slug={text_asset_slug}]")
        except ProtectedError as exc:
            raise ItqanError(
                error_name="related_objects_exist",
                message=str(_("Cannot delete Text asset because they are referenced through other objects")),
                status_code=400,
            ) from exc

    def _get_text_asset_version_or_404(
        self, text_asset_slug: str, version_id: int, publisher_q: Q | None = None
    ) -> AssetVersion:
        asset = self._get_text_asset_or_404(text_asset_slug, publisher_q=publisher_q)
        version = self.repo.get_text_asset_version(asset, version_id)
        if version is None:
            raise ItqanError(
                error_name="version_not_found",
                message=_("Version with id {id} not found for text asset {slug}.").format(
                    id=version_id, slug=text_asset_slug
                ),
                status_code=404,
            )
        return version

    def create_text_asset_version(
        self,
        text_asset_slug: str,
        *,
        text: VersionText | None = None,
        version_number: str | None = None,
        bump: VersionBump = "minor",
        file: Any = None,
        language: str | None = None,
        created_by_id: int | None = None,
        approved_by: User | None = None,
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """
        Business Logic: Create a new version for a text asset.

        Version creation, language assignment and file import run in one
        transaction so an unregistered language or an unparseable file rolls the
        whole thing back instead of leaving an orphaned version behind. The file
        must parse: its content is recorded as changes vs the previous version and
        has to be reviewed before it can be published, so nobody is notified here.

        The version is issued the next number in its language's sequence:
        ``version_number`` starts the sequence, otherwise the latest is bumped by ``bump``.

        With ``approved_by`` (a reviewer), the recorded changes are approved on
        upload under their name, so the version is publishable straight away.
        """
        asset = self._get_text_asset_or_404(text_asset_slug, publisher_q=publisher_q)
        with transaction.atomic():
            # Serialize with column changes and other commits of this asset, and refuse a
            # minor number when the columns were reordered since the last version.
            AssetContentRepository().lock_asset(asset)
            forbid_minor_after_column_reorder(asset, language or asset.language, bump)
            version = self.repo.create_text_asset_version(
                asset,
                name="",
                text=text,
                file=file,
                created_by_id=created_by_id,
            )
            set_version_language(version, language)
            if file:
                import_uploaded_file_into_entries(version, strict=True)
                AssetContentRepository().record_upload_changes(version)
                if approved_by is not None:
                    AssetReviewRepository().approve_changes(version.changes.all(), approved_by)
            # Numbered after the import, so a bad file is reported before a missing
            # number, and before the canonical file, which is named after it.
            name = issue_version_number(asset, language, start=version_number, bump=bump)
            version = self.repo.update_text_asset_version(version, fields={"name": name})
            if file:
                # Consumers download exactly what reviewers approve: the parsed entries.
                AssetContentRepository().store_canonical_file(version)
        logger.info(
            f"Text asset version created [version_id={version.pk}, asset_id={asset.pk}, slug={text_asset_slug}]"
        )
        return version

    def update_text_asset_version(
        self,
        text_asset_slug: str,
        version_id: int,
        fields: dict[str, Any],
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """
        Business Logic: Update an existing text asset version.
        """
        version = self._get_text_asset_version_or_404(text_asset_slug, version_id, publisher_q=publisher_q)
        # The version number is fixed once issued.
        fields = {key: value for key, value in fields.items() if key != "name"}
        with transaction.atomic():
            if fields.get("file_url"):
                # Version first, then the asset: the order publishing takes them in.
                version = lock_version_for_content_change(version)
                AssetContentRepository().lock_asset(version.asset)
            updated = self.repo.update_text_asset_version(version, fields=fields)
            if fields.get("file_url"):
                adopt_current_columns(updated)
                # New content: re-recorded as changes, so it is reviewed again.
                import_uploaded_file_into_entries(updated, strict=True)
                AssetContentRepository().record_upload_changes(updated)
                AssetContentRepository().store_canonical_file(updated)
        logger.info(f"Text asset version updated [version_id={version_id}, asset_slug={text_asset_slug}]")
        return updated

    def delete_text_asset_version(
        self, text_asset_slug: str, version_id: int, publisher_q: Q | None = None, *, confirm_unpublish: bool = False
    ) -> None:
        """
        Business Logic: Delete a text asset version.
        """
        version = self._get_text_asset_version_or_404(text_asset_slug, version_id, publisher_q=publisher_q)
        with transaction.atomic():
            version = lock_version_for_delete(version, confirm_unpublish=confirm_unpublish)
            was_published = AssetContentRepository().unpublish_version(version)
            self.repo.delete_text_asset_version(version)
        logger.info(
            f"Text asset version deleted [version_id={version_id}, asset_slug={text_asset_slug}, was_published={was_published}]"
        )
