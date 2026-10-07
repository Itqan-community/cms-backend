from __future__ import annotations

from collections import defaultdict

from django.db.models import F, IntegerField, OuterRef, Q, QuerySet, Subquery, Window
from django.db.models.functions import Coalesce, RowNumber

from apps.content.models import Asset, AssetVersion, AssetVersionChange, ReviewStateChoice, VersionStateChoice


def change_language(change: AssetVersionChange) -> str:
    """The language a change belongs to — its version's language."""
    return change.version.resolved_language


class AssetReviewRepository:
    def _language_q(self, asset: Asset, language: str) -> Q:
        language_q = Q(version__asset_language__language=language)
        if language == asset.language:
            language_q |= Q(version__asset_language__isnull=True)
        return language_q

    @staticmethod
    def _unit_key() -> Coalesce:
        """The per-asset unit key of a change row (see ``changes_for``)."""
        return Coalesce("sura_id", "ayah_id", "word_id", "page_no", output_field=IntegerField())

    def pending_units_by_version(self, asset: Asset, language: str) -> dict[int, int]:
        """``{version_id: units awaiting approval}`` for every committed version of
        (asset, language). A version is fully approved when its count is 0.

        A unit awaits approval at version V when its most recent change at or
        before V is not approved (unreviewed or commented) — the same "latest
        change per unit" the review page shows, evaluated as of V. Units with no
        change rows (content that predates change tracking) never await approval.
        One pass over the language's change rows, oldest commit first.
        """
        version_language_q = Q(asset_language__language=language)
        if language == asset.language:
            version_language_q |= Q(asset_language__isnull=True)
        version_ids = list(
            AssetVersion.objects.filter(asset=asset, state=VersionStateChoice.PUBLISHED)
            .filter(version_language_q)
            .order_by("created_at", "id")
            .values_list("id", flat=True)
        )
        changes_by_version: dict[int, list[tuple[int, str | None]]] = defaultdict(list)
        rows = (
            AssetVersionChange.objects.filter(version_id__in=version_ids)
            .annotate(unit_key=self._unit_key())
            .values_list("version_id", "unit_key", "review__state")
        )
        for version_id, unit_key, review_state in rows.iterator():
            changes_by_version[version_id].append((unit_key, review_state))

        pending: set[int] = set()
        result: dict[int, int] = {}
        for version_id in version_ids:
            for unit_key, review_state in changes_by_version.get(version_id, ()):
                if review_state == ReviewStateChoice.APPROVED:
                    pending.discard(unit_key)
                else:
                    pending.add(unit_key)
            result[version_id] = len(pending)
        return result

    def changes_for(
        self,
        asset: Asset,
        language: str,
        *,
        state: str | None = None,
        as_of: AssetVersion | None = None,
    ) -> QuerySet[AssetVersionChange]:
        """The reviewable changes for one (asset, language), newest commit first.

        Without ``as_of``: **every** change ever committed, including ones a later
        commit replaced — each version's own text can then be approved, so any
        version can be published once its changes are.

        With ``as_of`` (a committed version): the changes that make up that
        version — the latest change per unit among commits up to and including
        it. Exactly these decide whether it is approved
        (``pending_units_by_version``), so this answers "why is it not approved".

        Each row is annotated with ``baseline_text``: the unit's text at its most
        recent *approved* change in an earlier commit, so the reviewer sees the net
        ``last-approved -> this change`` diff (empty when the unit was never
        approved before it; the portal then compares with ``old_text``).

        A change row is keyed to exactly one of ``sura``/``ayah``/``word``/``page_no``,
        chosen by the asset's ``template`` — which is immutable after creation, so
        every change row for a given asset shares exactly one unit kind. That makes
        ``Coalesce`` of the four columns an unambiguous per-asset unit key: ids
        cannot collide across unit kinds within one asset's change set.
        """
        language_q = self._language_q(asset, language)
        unit_key = self._unit_key()
        scope = AssetVersionChange.objects.filter(version__asset=asset).filter(language_q)
        if as_of is None:
            qs = scope
        else:
            # Commits up to and including `as_of`, in the same (created_at, id)
            # order the approval pass uses.
            up_to = Q(version__created_at__lt=as_of.created_at) | Q(
                version__created_at=as_of.created_at, version_id__lte=as_of.id
            )
            # The latest change row per unit among them. Postgres DISTINCT ON only
            # accepts real field paths, not an annotated expression like
            # `unit_key`, so this ranks rows within each unit (newest commit
            # first) and keeps rank 1; filtering on a Window annotation makes
            # Django wrap it in a subquery, which is the shape wanted here.
            latest_pks = (
                scope.filter(up_to)
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
            qs = AssetVersionChange.objects.filter(pk__in=Subquery(latest_pks))
        # Correlated: the new_text of this unit's latest approved change in an
        # earlier commit than the row's own.
        earlier_approved_text = (
            AssetVersionChange.objects.filter(version__asset=asset, review__state=ReviewStateChoice.APPROVED)
            .filter(language_q)
            .annotate(unit_key=unit_key)
            .filter(unit_key=OuterRef("unit_key"))
            .filter(
                Q(version__created_at__lt=OuterRef("version__created_at"))
                | Q(version__created_at=OuterRef("version__created_at"), version_id__lt=OuterRef("version_id"))
            )
            .order_by("-version__created_at", "-version_id")
            .values("new_text")[:1]
        )
        qs = (
            qs.annotate(unit_key=unit_key)
            .select_related(
                "ayah",
                "ayah__sura",
                "sura",
                "word__ayah",
                "word__sura",
                "version",
                "version__asset",
                "version__created_by",
                "review",
                "review__reviewed_by",
            )
            .annotate(baseline_text=Subquery(earlier_approved_text))
        )
        if state == "unreviewed":
            qs = qs.filter(review__isnull=True)
        elif state in (ReviewStateChoice.APPROVED, ReviewStateChoice.COMMENTED):
            qs = qs.filter(review__state=state)
        return qs.order_by("-version__created_at", "-version_id", "order", "unit_key")

    def committed_versions(self, asset: Asset, language: str) -> QuerySet[AssetVersion]:
        """The committed versions of (asset, language), newest first — the review
        page's version filter."""
        language_q = Q(asset_language__language=language)
        if language == asset.language:
            language_q |= Q(asset_language__isnull=True)
        return (
            AssetVersion.objects.filter(asset=asset, state=VersionStateChoice.PUBLISHED)
            .filter(language_q)
            .order_by("-created_at", "-id")
        )

    def get_change(self, asset: Asset, change_id: int) -> AssetVersionChange | None:
        return (
            AssetVersionChange.objects.filter(version__asset=asset, pk=change_id)
            .select_related("version", "version__asset_language", "version__asset", "version__created_by", "review")
            .first()
        )
