from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.content.models import Asset, AssetVersionChange, ReviewStateChoice


def change_language(change: AssetVersionChange) -> str:
    """The language a change belongs to: its version's asset_language, else the
    asset's source language (legacy rows with no asset_language)."""
    version = change.version
    if version.asset_language_id:
        return version.asset_language.language
    return version.asset.language


class AssetReviewRepository:
    def changes_for(self, asset: Asset, language: str, *, state: str | None = None) -> QuerySet[AssetVersionChange]:
        """All change rows for one (asset, language), newest-commit first, with the
        review prefetched. Optional state filter (unreviewed/approved/commented)."""
        language_q = Q(version__asset_language__language=language)
        if language == asset.language:
            language_q |= Q(version__asset_language__isnull=True)
        qs = (
            AssetVersionChange.objects.filter(version__asset=asset)
            .filter(language_q)
            .select_related("ayah", "ayah__sura", "version", "review", "review__reviewed_by")
        )
        if state == "unreviewed":
            qs = qs.filter(review__isnull=True)
        elif state in (ReviewStateChoice.APPROVED, ReviewStateChoice.COMMENTED):
            qs = qs.filter(review__state=state)
        return qs.order_by("-version__created_at", "-version_id", "order", "ayah_id")

    def get_change(self, asset: Asset, change_id: int) -> AssetVersionChange | None:
        return (
            AssetVersionChange.objects.filter(version__asset=asset, pk=change_id)
            .select_related("version", "version__asset_language", "version__asset", "review")
            .first()
        )
