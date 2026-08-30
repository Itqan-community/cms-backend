from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.content.cache import invalidate_recitation_folder_cache
from apps.content.models import RecitationFolder
from apps.content.repositories.recitation_folder import RecitationFolderRepository
from apps.content.services.admin.asset_recitation_json_file_sync_service import (
    sync_asset_recitations_json_file,
    unpublish_folder_recitations_json,
)
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
        fields: dict[str, Any],
        publisher_q: Q | None = None,
    ) -> RecitationFolder:
        """
        Business Logic: update a folder's names, visibility, or default status.

        The slug is left alone on rename: it is the public ``?folder=`` value, and
        changing it would break links and cached responses already pointing at it.
        """
        folder = self.get_folder_or_404(asset_id, folder_slug, publisher_q=publisher_q)

        if "is_default" in fields:
            is_default = fields.pop("is_default")
            if is_default is False:
                raise ItqanError(
                    error_name="cannot_unset_default_folder",
                    message=_("Use another folder's set-default action instead of clearing the default flag."),
                    status_code=400,
                )
            if is_default is True:
                return self._promote_to_default(folder)

        visibility_changed = False
        if "is_visible" in fields:
            is_visible = fields.pop("is_visible")
            if is_visible is False and folder.is_default:
                raise ItqanError(
                    error_name="cannot_hide_default_folder",
                    message=_("The default folder cannot be hidden."),
                    status_code=400,
                )
            if is_visible is not None and is_visible != folder.is_visible:
                folder.is_visible = is_visible
                visibility_changed = True
                logger.info(f"Recitation folder visibility changed [folder_id={folder.pk}, is_visible={is_visible}]")

        name_fields = {k: v for k, v in fields.items() if k in ("name_ar", "name_en")}
        if name_fields:
            for field in ("name_ar", "name_en"):
                if field in name_fields:
                    name_fields[field] = (name_fields[field] or "").strip()

            final_name_ar = name_fields.get("name_ar", folder.name_ar) or ""
            final_name_en = name_fields.get("name_en", folder.name_en) or ""
            if not final_name_ar and not final_name_en:
                raise ItqanError(
                    error_name="folder_name_required",
                    message=_("Folder name (Arabic or English) is required."),
                    status_code=400,
                )

            ordered_fields: dict[str, str | None] = {"name": final_name_ar or final_name_en}
            ordered_fields.update(name_fields)
            folder = self.repo.update_folder(folder, fields=ordered_fields)
        elif visibility_changed:
            folder.save(update_fields=["is_visible", "updated_at"])

        if visibility_changed:
            if folder.is_visible:
                sync_asset_recitations_json_file(asset_id, folder_id=folder.pk)
            else:
                unpublish_folder_recitations_json(asset_id, folder_id=folder.pk)
            invalidate_recitation_folder_cache(asset_id, folder)

        if name_fields or visibility_changed:
            logger.info(f"Recitation folder updated [folder_id={folder.pk}, asset_id={asset_id}]")
        return folder

    def _promote_to_default(self, folder: RecitationFolder) -> RecitationFolder:
        if folder.is_default:
            return folder

        if not folder.is_visible:
            raise ItqanError(
                error_name="cannot_set_hidden_folder_as_default",
                message=_("A hidden folder cannot be set as the default."),
                status_code=400,
            )

        with transaction.atomic():
            RecitationFolder.objects.filter(asset_id=folder.asset_id, is_default=True).update(is_default=False)
            folder.is_default = True
            folder.save(update_fields=["is_default", "updated_at"])

        logger.info(
            f"Recitation folder promoted to default [folder_id={folder.pk}, asset_id={folder.asset_id}, slug={folder.slug}]"
        )
        invalidate_recitation_folder_cache(folder.asset_id, folder)
        return folder

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

        asset_id = folder.asset_id
        self.repo.delete_folder(folder)
        invalidate_recitation_folder_cache(asset_id, folder)
        logger.info(f"Recitation folder deleted [asset_id={asset_id}, slug={folder_slug}]")
