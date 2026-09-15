from __future__ import annotations

from django.db.models import OuterRef, Q, QuerySet, Subquery

from apps.content.models import Asset, AssetVersionChange, ReviewStateChoice


def change_language(change: AssetVersionChange) -> str:
    """The language a change belongs to — its version's language."""
    return change.version.resolved_language


class AssetReviewRepository:
    def _language_q(self, asset: Asset, language: str) -> Q:
        language_q = Q(version__asset_language__language=language)
        if language == asset.language:
            language_q |= Q(version__asset_language__isnull=True)
        return language_q

    def changes_for(self, asset: Asset, language: str, *, state: str | None = None) -> QuerySet[AssetVersionChange]:
        """The reviewable changes for one (asset, language): the **latest change per
        ayah** only (superseded intermediate edits are not reviewed on their own),
        newest-commit first.

        Each row is annotated with ``baseline_text`` — the text at the ayah's most
        recent *approved* change (the last-approved text) — so the reviewer sees the
        net ``last-approved → current`` diff rather than an intermediate transition.
        """
        language_q = self._language_q(asset, language)
        # The latest change row per ayah (its new_text is the current head text).
        latest_pks = (
            AssetVersionChange.objects.filter(version__asset=asset)
            .filter(language_q)
            .order_by("ayah_id", "-version__created_at", "-version_id")
            .distinct("ayah_id")
            .values("pk")
        )
        # Correlated: the new_text of this ayah's most recent approved change.
        last_approved_text = (
            AssetVersionChange.objects.filter(version__asset=asset, review__state=ReviewStateChoice.APPROVED)
            .filter(language_q)
            .filter(ayah_id=OuterRef("ayah_id"))
            .order_by("-version__created_at", "-version_id")
            .values("new_text")[:1]
        )
        qs = (
            AssetVersionChange.objects.filter(pk__in=Subquery(latest_pks))
            .select_related("ayah", "ayah__sura", "version", "review", "review__reviewed_by")
            .annotate(baseline_text=Subquery(last_approved_text))
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
