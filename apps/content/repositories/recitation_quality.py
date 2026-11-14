from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, OuterRef, Q

from apps.content.models import RecitationQuality
from apps.content.timing_coverage import timing_coverage_subqueries

if TYPE_CHECKING:
    from django.db.models import QuerySet


class RecitationQualityRepository:
    def __init__(self) -> None:
        self.model = RecitationQuality

    def list_for_asset(self, asset_id: int, annotate_tracks_count: bool = False) -> QuerySet[RecitationQuality]:
        """Return an asset's qualities, default first then alphabetically."""
        qs = self.model.objects.filter(asset_id=asset_id)
        if annotate_tracks_count:
            qs = qs.annotate(tracks_count=Count("tracks"), **timing_coverage_subqueries(Q(quality=OuterRef("pk"))))
        return qs.order_by("-is_default", "name")

    def get_by_slug(self, asset_id: int, slug: str, publisher_q: Q | None = None) -> RecitationQuality | None:
        """Return a single quality by its per-asset slug, or None when it does not exist."""
        qs = self.model.objects.filter(asset_id=asset_id, slug=slug)
        if publisher_q is not None:
            qs = qs.filter(publisher_q)
        return qs.first()

    def get_default_for_asset(self, asset_id: int) -> RecitationQuality | None:
        """
        Return the asset's default quality.

        Every recitation asset is given one at creation time (and existing assets were
        backfilled by migration 0048), so a missing default means the asset predates
        the quality feature or was created outside the service layer.
        """
        return self.model.objects.filter(asset_id=asset_id, is_default=True).first()

    def create_quality(
        self,
        *,
        asset_id: int,
        name: str,
        name_ar: str | None = None,
        name_en: str | None = None,
        is_default: bool = False,
    ) -> RecitationQuality:
        """Persist a new quality. The slug is derived from the name by the model."""
        return self.model.objects.create(
            asset_id=asset_id,
            name=name,
            name_ar=name_ar,
            name_en=name_en,
            is_default=is_default,
        )

    def update_quality(self, quality: RecitationQuality, fields: dict[str, str | bool | None]) -> RecitationQuality:
        """Apply field updates to a quality and save it."""
        for field, value in fields.items():
            setattr(quality, field, value)
        quality.save()
        return quality

    def delete_quality(self, quality: RecitationQuality) -> None:
        """Delete a quality. Its tracks and their ayah timings cascade with it."""
        quality.delete()
