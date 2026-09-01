from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, Q

from apps.content.models import RecitationFolder

if TYPE_CHECKING:
    from django.db.models import QuerySet


class RecitationFolderRepository:
    def __init__(self) -> None:
        self.model = RecitationFolder

    def list_for_asset(self, asset_id: int, annotate_tracks_count: bool = False) -> QuerySet[RecitationFolder]:
        """Return an asset's folders, default first then alphabetically."""
        qs = self.model.objects.filter(asset_id=asset_id)
        if annotate_tracks_count:
            qs = qs.annotate(tracks_count=Count("tracks"))
        return qs.order_by("-is_default", "name")

    def get_by_slug(self, asset_id: int, slug: str, publisher_q: Q | None = None) -> RecitationFolder | None:
        """Return a single folder by its per-asset slug, or None when it does not exist."""
        qs = self.model.objects.filter(asset_id=asset_id, slug=slug)
        if publisher_q is not None:
            qs = qs.filter(publisher_q)
        return qs.first()

    def get_default_for_asset(self, asset_id: int) -> RecitationFolder | None:
        """
        Return the asset's default folder.

        Every recitation asset is given one at creation time (and existing assets were
        backfilled by migration 0048), so a missing default means the asset predates
        the folder feature or was created outside the service layer.
        """
        return self.model.objects.filter(asset_id=asset_id, is_default=True).first()

    def create_folder(
        self,
        *,
        asset_id: int,
        name: str,
        name_ar: str | None = None,
        name_en: str | None = None,
        is_default: bool = False,
    ) -> RecitationFolder:
        """Persist a new folder. The slug is derived from the name by the model."""
        return self.model.objects.create(
            asset_id=asset_id,
            name=name,
            name_ar=name_ar,
            name_en=name_en,
            is_default=is_default,
        )

    def update_folder(self, folder: RecitationFolder, fields: dict[str, str | bool | None]) -> RecitationFolder:
        """Apply field updates to a folder and save it."""
        for field, value in fields.items():
            setattr(folder, field, value)
        folder.save()
        return folder

    def delete_folder(self, folder: RecitationFolder) -> None:
        """Delete a folder. Its tracks and their ayah timings cascade with it."""
        folder.delete()
