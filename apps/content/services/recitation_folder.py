from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.content.models import RecitationFolder
from apps.content.repositories.recitation_folder import RecitationFolderRepository
from apps.core.ninja_utils.errors import ItqanError

if TYPE_CHECKING:
    from django.db.models import QuerySet

logger = logging.getLogger(__name__)


class RecitationFolderService:
    def __init__(self, repo: RecitationFolderRepository | None = None) -> None:
        self.repo = repo or RecitationFolderRepository()

    def list_folders(self, asset_id: int, annotate_tracks_count: bool = False) -> QuerySet[RecitationFolder]:
        """Business Logic: list an asset's folders."""
        return self.repo.list_for_asset(asset_id, annotate_tracks_count=annotate_tracks_count)

    def get_folder_or_404(self, asset_id: int, folder_slug: str, publisher_q: Q | None = None) -> RecitationFolder:
        """Business Logic: resolve a folder by slug, raising a typed 404 when absent."""
        folder = self.repo.get_by_slug(asset_id, folder_slug, publisher_q=publisher_q)
        if folder is None:
            raise ItqanError(
                error_name="folder_not_found",
                message=_("Folder with slug {slug} not found.").format(slug=folder_slug),
                status_code=404,
            )
        return folder

    def resolve_folder(self, asset_id: int, folder_slug: str | None, publisher_q: Q | None = None) -> RecitationFolder:
        """
        Business Logic: resolve the folder a request is asking for.

        An explicit slug must exist (404 otherwise). Without one, the asset's
        default folder is served, which is what keeps pre-folder API callers working.
        """
        if folder_slug is not None:
            return self.get_folder_or_404(asset_id, folder_slug, publisher_q=publisher_q)

        default_folder = self.repo.get_default_for_asset(asset_id)
        if default_folder is None:
            # Every recitation gets a default folder at creation, and existing ones
            # were backfilled, so this means the asset was built outside the service
            # layer. Surface it rather than silently returning no tracks.
            logger.error(f"Recitation asset has no default folder [asset_id={asset_id}]")
            raise ItqanError(
                error_name="folder_not_found",
                message=_("This recitation has no default folder."),
                status_code=404,
            )
        return default_folder

    def create_folder(
        self,
        *,
        asset_id: int,
        name_ar: str,
        name_en: str,
    ) -> RecitationFolder:
        """Business Logic: add a variant folder to a recitation."""
        normalized_name_ar = (name_ar or "").strip()
        normalized_name_en = (name_en or "").strip()

        name = normalized_name_ar or normalized_name_en
        if not name:
            raise ItqanError(
                error_name="folder_name_required",
                message=_("Folder name (Arabic or English) is required."),
                status_code=400,
            )

        folder = self.repo.create_folder(
            asset_id=asset_id,
            name=name,
            name_ar=normalized_name_ar,
            name_en=normalized_name_en,
            is_default=False,
        )
        logger.info(f"Recitation folder created [folder_id={folder.pk}, asset_id={asset_id}, slug={folder.slug}]")
        return folder

    def update_folder(
        self,
        *,
        asset_id: int,
        folder_slug: str,
        fields: dict[str, str | None],
        publisher_q: Q | None = None,
    ) -> RecitationFolder:
        """
        Business Logic: rename a folder.

        The slug is left alone on rename: it is the public ``?folder=`` value, and
        changing it would break links and cached responses already pointing at it.
        """
        folder = self.get_folder_or_404(asset_id, folder_slug, publisher_q=publisher_q)

        for field in ("name_ar", "name_en"):
            if field in fields:
                fields[field] = (fields[field] or "").strip()

        final_name_ar = fields.get("name_ar", folder.name_ar) or ""
        final_name_en = fields.get("name_en", folder.name_en) or ""
        if not final_name_ar and not final_name_en:
            raise ItqanError(
                error_name="folder_name_required",
                message=_("Folder name (Arabic or English) is required."),
                status_code=400,
            )

        # `name` is a modeltranslation descriptor that writes through to the active
        # language's column, so it must be applied *before* the explicit name_ar /
        # name_en values — otherwise it silently overwrites one of them.
        ordered_fields: dict[str, str | None] = {"name": final_name_ar or final_name_en}
        ordered_fields.update(fields)

        updated = self.repo.update_folder(folder, fields=ordered_fields)
        logger.info(f"Recitation folder updated [folder_id={updated.pk}, asset_id={asset_id}]")
        return updated

    def delete_folder(self, *, asset_id: int, folder_slug: str, publisher_q: Q | None = None) -> None:
        """
        Business Logic: delete a variant folder and everything inside it.

        The default folder is protected: it is what the APIs fall back to when no
        folder is named, so removing it would break every caller of this recitation.
        """
        folder = self.get_folder_or_404(asset_id, folder_slug, publisher_q=publisher_q)

        if folder.is_default:
            raise ItqanError(
                error_name="cannot_delete_default_folder",
                message=_("The default folder cannot be deleted."),
                status_code=400,
            )

        self.repo.delete_folder(folder)
        logger.info(f"Recitation folder deleted [asset_id={asset_id}, slug={folder_slug}]")
