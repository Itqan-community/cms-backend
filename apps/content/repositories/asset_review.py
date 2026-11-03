from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import reduce
import operator
from typing import TYPE_CHECKING

from django.db.models import F, OuterRef, Q, QuerySet, Subquery, Value, Window
from django.db.models.functions import Coalesce, RowNumber
from django.utils import timezone
from simple_history.utils import bulk_create_with_history, bulk_update_with_history

from apps.content.models import (
    Asset,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    ReviewStateChoice,
    VersionStateChoice,
)
from apps.content.services.asset_templates import ColumnFilter, _normalized
from apps.content.unit_keys import unit_key_expression

if TYPE_CHECKING:
    from apps.users.models import User


def change_language(change: AssetVersionChange) -> str:
    """The language a change belongs to — its version's language."""
    return change.version.resolved_language


# The unit's surah number and ayah-in-surah number, whichever unit field the
# change row is keyed to (a range by its start; pages have neither).
_SURAH_NUMBER = Coalesce("surah_id", "ayah__surah_id", "word__surah_id", "from_ayah__surah_id", "from_word__surah_id")
_AYAH_NUMBER = Coalesce(
    "ayah__number_in_surah",
    "word__ayah__number_in_surah",
    "from_ayah__number_in_surah",
    "from_word__ayah__number_in_surah",
)
# Text filters per review-grid column, over these fields (a missing value is "").
_TEXT_FILTER_FIELDS: dict[str, str] = {
    "change_type": "change_type",
    "column": "column__key",
    "commit_ref": "version__name",
    "edited_by": "version__created_by__name",
    "reviewed_by": "review__reviewed_by__name",
    "comment": "review__comment",
}


@dataclass(frozen=True)
class ReviewFilters:
    """The review grid's column filters, applied before paging (and bulk approve).

    ``text`` matches a change's text before **or** after it (``old_text`` /
    ``new_text``); a negated condition (``notContains``, ``notEqual``) and
    ``blank`` must then hold on both sides. ``unit_surah`` and ``surah`` both
    filter the unit's surah number, ``ayah`` its ayah-in-surah number. ``texts``
    is keyed by ``_TEXT_FILTER_FIELDS``.
    """

    text: ColumnFilter | None = None
    texts: Mapping[str, ColumnFilter] = field(default_factory=dict)
    unit_surah: ColumnFilter | None = None
    surah: ColumnFilter | None = None
    ayah: ColumnFilter | None = None

    def apply(self, qs: QuerySet[AssetVersionChange]) -> QuerySet[AssetVersionChange]:
        for key, column_filter in self.texts.items():
            name = f"_filter_{key}"
            qs = qs.annotate(**{name: _normalized(Coalesce(F(_TEXT_FILTER_FIELDS[key]), Value("")))}).filter(
                column_filter.q(name)
            )
        if self.text is not None:
            qs = qs.annotate(_filter_old=_normalized(F("old_text")), _filter_new=_normalized(F("new_text"))).filter(
                self._either_text_q(self.text)
            )
        numbers = ((self.unit_surah, _SURAH_NUMBER), (self.surah, _SURAH_NUMBER), (self.ayah, _AYAH_NUMBER))
        for index, (number_filter, expression) in enumerate(numbers):
            if number_filter is not None:
                name = f"_filter_number_{index}"
                qs = qs.annotate(**{name: expression}).filter(number_filter.q(name))
        return qs

    @staticmethod
    def _either_text_q(text_filter: ColumnFilter) -> Q:
        def side_q(condition) -> Q:
            both = condition.type in ("notContains", "notEqual", "blank")
            join = operator.and_ if both else operator.or_
            return join(condition.q("_filter_old"), condition.q("_filter_new"))

        join = operator.and_ if text_filter.operator == "AND" else operator.or_
        return reduce(join, (side_q(condition) for condition in text_filter.conditions))


class AssetReviewRepository:
    def _language_q(self, asset: Asset, language: str) -> Q:
        language_q = Q(version__asset_language__language=language)
        if language == asset.language:
            language_q |= Q(version__asset_language__isnull=True)
        return language_q

    @staticmethod
    def _unit_key() -> Coalesce:
        """The per-asset unit key of a change row (see ``changes_for``)."""
        return unit_key_expression()

    def pending_cells_by_version(self, asset: Asset, language: str) -> dict[int, int]:
        """``{version_id: cells awaiting approval}`` for every committed version of
        (asset, language). A version is fully approved when its count is 0.

        A cell — (unit, column) — awaits approval at version V when its most
        recent change at or before V is not approved (unreviewed or commented) —
        the same "latest change per cell" the review page shows, evaluated as of
        V. Cells with no change rows (content that predates change tracking)
        never await approval.
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
        changes_by_version: dict[int, list[tuple[tuple[int, int], str | None]]] = defaultdict(list)
        rows = (
            AssetVersionChange.objects.filter(version_id__in=version_ids)
            .annotate(unit_key=self._unit_key())
            .values_list("version_id", "unit_key", "column_id", "review__state")
        )
        for version_id, unit_key, column_id, review_state in rows.iterator():
            # A cell — (unit, column) — is what awaits approval.
            changes_by_version[version_id].append(((unit_key, column_id), review_state))

        pending: set[tuple[int, int]] = set()
        result: dict[int, int] = {}
        for version_id in version_ids:
            for cell, review_state in changes_by_version.get(version_id, ()):
                if review_state == ReviewStateChoice.APPROVED:
                    pending.discard(cell)
                else:
                    pending.add(cell)
            result[version_id] = len(pending)
        return result

    def changes_for(
        self,
        asset: Asset,
        language: str,
        *,
        state: str | None = None,
        as_of: AssetVersion | None = None,
        filters: ReviewFilters | None = None,
    ) -> QuerySet[AssetVersionChange]:
        """The reviewable changes for one (asset, language), newest commit first.

        Without ``as_of``: **every** change ever committed, including ones a later
        commit replaced — each version's own text can then be approved, so any
        version can be published once its changes are.

        With ``as_of`` (a committed version): the changes that make up that
        version — the latest change per unit among commits up to and including
        it. Exactly these decide whether it is approved
        (``pending_cells_by_version``), so this answers "why is it not approved".

        Each row is annotated with ``baseline_text``: the unit's text at its most
        recent *approved* change in an earlier commit, so the reviewer sees the net
        ``last-approved -> this change`` diff (empty when the unit was never
        approved before it; the portal then compares with ``old_text``).

        A change row is keyed to exactly one unit — a ``surah``/``ayah``/``word``/
        ``page_no``, or an ayah / word range — chosen by the asset's ``template``,
        which is immutable after creation, so every change row for a given asset
        shares exactly one unit kind. ``unit_key_expression`` (the SQL twin of
        ``AssetVersionChange.unit_id``) is therefore an unambiguous per-asset unit
        key: ids cannot collide across unit kinds within one asset's change set.

        ``filters`` (the review grid's column filters) narrow the result after
        ``as_of`` picks the changes that make up a version, so a filter never
        changes which change counts as a unit's latest.
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
                        partition_by=[unit_key, F("column_id")],
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
            .filter(unit_key=OuterRef("unit_key"), column_id=OuterRef("column_id"))
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
                "ayah__surah",
                "surah",
                "word__ayah",
                "word__surah",
                "from_ayah",
                "to_ayah",
                "from_word__ayah",
                "to_word__ayah",
                "version",
                "version__asset",
                "version__created_by",
                "review",
                "review__reviewed_by",
                "column",
            )
            .annotate(baseline_text=Subquery(earlier_approved_text))
        )
        if state == "unreviewed":
            qs = qs.filter(review__isnull=True)
        elif state in (ReviewStateChoice.APPROVED, ReviewStateChoice.COMMENTED):
            qs = qs.filter(review__state=state)
        if filters is not None:
            qs = filters.apply(qs)
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

    def approve_changes(self, changes: QuerySet[AssetVersionChange], user: User) -> int:
        """Approve ``changes`` as ``user`` and return how many were approved.

        Unreviewed changes get a review row and commented ones are flipped to
        approved (their comment cleared). Already-approved changes are skipped so
        they keep the auditing of whoever approved them.
        """
        rows = list(changes.exclude(review__state=ReviewStateChoice.APPROVED).values_list("pk", "review__pk"))
        if not rows:
            return 0
        now = timezone.now()
        commented = list(AssetVersionChangeReview.objects.filter(pk__in=[review for _, review in rows if review]))
        for review in commented:
            review.state = ReviewStateChoice.APPROVED
            review.comment = ""
            review.reviewed_by = user
            review.reviewed_at = now
            review.updated_at = now
        if commented:
            bulk_update_with_history(
                commented,
                AssetVersionChangeReview,
                ["state", "comment", "reviewed_by", "reviewed_at", "updated_at"],
                batch_size=1000,
                default_user=user,
            )
        unreviewed = [
            AssetVersionChangeReview(
                change_id=change, state=ReviewStateChoice.APPROVED, reviewed_by=user, reviewed_at=now
            )
            for change, review in rows
            if review is None
        ]
        if unreviewed:
            bulk_create_with_history(unreviewed, AssetVersionChangeReview, batch_size=1000, default_user=user)
        return len(rows)
