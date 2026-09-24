from __future__ import annotations

from django.db.models import F, IntegerField, OuterRef, Q, QuerySet, Subquery, Window
from django.db.models.functions import Coalesce, RowNumber

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
        unit** only (superseded intermediate edits are not reviewed on their own),
        newest-commit first.

        Each row is annotated with ``baseline_text`` — the text at the unit's most
        recent *approved* change (the last-approved text) — so the reviewer sees the
        net ``last-approved -> current`` diff rather than an intermediate transition.

        A change row is keyed to exactly one of ``sura``/``ayah``/``word``/``page_no``,
        chosen by the asset's ``template`` — which is immutable after creation, so
        every change row for a given asset shares exactly one unit kind. That makes
        ``Coalesce`` of the four columns an unambiguous per-asset unit key: ids
        cannot collide across unit kinds within one asset's change set. Both the
        dedup and the baseline correlation key on it, so the same "latest"/"last
        approved" semantics that used to apply only to ayah rows now apply to all
        four templates.
        """
        language_q = self._language_q(asset, language)
        unit_key = Coalesce("sura_id", "ayah_id", "word_id", "page_no", output_field=IntegerField())
        # The latest change row per unit (its new_text is the current head text).
        # Postgres DISTINCT ON only accepts real field paths, not an annotated
        # expression like `unit_key` (Django's compiler resolves distinct()
        # arguments against model fields, never annotations) — so this uses a
        # ranked-window instead: rank rows within each unit, newest commit
        # first, and keep rank 1. Filtering on a Window annotation forces
        # Django to wrap the query in a subquery, which is exactly the shape
        # we want here.
        latest_pks = (
            AssetVersionChange.objects.filter(version__asset=asset)
            .filter(language_q)
            .annotate(
                rank=Window(
                    expression=RowNumber(),
                    partition_by=[unit_key],
                    order_by=[F("version__created_at").desc(), F("version_id").desc()],
                )
            )
            .filter(rank=1)
            .values("pk")
        )
        # Correlated: the new_text of this unit's most recent approved change.
        last_approved_text = (
            AssetVersionChange.objects.filter(version__asset=asset, review__state=ReviewStateChoice.APPROVED)
            .filter(language_q)
            .annotate(unit_key=unit_key)
            .filter(unit_key=OuterRef("unit_key"))
            .order_by("-version__created_at", "-version_id")
            .values("new_text")[:1]
        )
        qs = (
            AssetVersionChange.objects.filter(pk__in=Subquery(latest_pks))
            .annotate(unit_key=unit_key)
            .select_related(
                "ayah",
                "ayah__sura",
                "sura",
                "word__ayah",
                "word__sura",
                "version",
                "version__asset",
                "review",
                "review__reviewed_by",
            )
            .annotate(baseline_text=Subquery(last_approved_text))
        )
        if state == "unreviewed":
            qs = qs.filter(review__isnull=True)
        elif state in (ReviewStateChoice.APPROVED, ReviewStateChoice.COMMENTED):
            qs = qs.filter(review__state=state)
        return qs.order_by("-version__created_at", "-version_id", "order", "unit_key")

    def get_change(self, asset: Asset, change_id: int) -> AssetVersionChange | None:
        return (
            AssetVersionChange.objects.filter(version__asset=asset, pk=change_id)
            .select_related("version", "version__asset_language", "version__asset", "review")
            .first()
        )
