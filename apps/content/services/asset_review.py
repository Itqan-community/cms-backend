from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.content.models import (
    Asset,
    AssetVersionChange,
    AssetVersionChangeReview,
    CategoryChoice,
    ReviewStateChoice,
    StatusChoice,
)
from apps.content.repositories.asset_review import AssetReviewRepository, change_language
from apps.content.services.asset_language_access import allowed_languages, require_language
from apps.core.ninja_utils.errors import ItqanError

_NOT_FOUND_ERROR = {
    CategoryChoice.TRANSLATION: "translation_not_found",
    CategoryChoice.TAFSIR: "tafsir_not_found",
}


class AssetReviewService:
    def __init__(self, repo: AssetReviewRepository | None = None) -> None:
        self.repo = repo or AssetReviewRepository()

    def _get_asset_or_404(self, slug: str, category: CategoryChoice, publisher_q: Q | None = None) -> Asset:
        qs = Asset.objects.all()
        if publisher_q is not None:
            qs = qs.filter(publisher_q)
        try:
            return qs.get(slug=slug, category=category, status=StatusChoice.READY)
        except Asset.DoesNotExist as exc:
            raise ItqanError(
                error_name=_NOT_FOUND_ERROR[category],
                message=_("{category} with slug {slug} not found.").format(category=category.label, slug=slug),
                status_code=404,
            ) from exc

    def _require_assigned(self, user, asset: Asset, language: str) -> None:
        require_language(user, asset, language)

    def list_review_languages(
        self, slug: str, category: CategoryChoice, *, user, publisher_q: Q | None = None
    ) -> list[str]:
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        asset_languages = set(asset.languages.values_list("language", flat=True))
        asset_languages.add(asset.language)  # source, even when the row is created lazily
        return sorted(asset_languages & allowed_languages(user, asset))

    def list_changes(
        self,
        slug: str,
        category: CategoryChoice,
        *,
        language: str,
        user,
        state: str | None,
        publisher_q: Q | None = None,
    ) -> QuerySet[AssetVersionChange]:
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        self._require_assigned(user, asset, language)
        return self.repo.changes_for(asset, language, state=state)

    def set_review_state(
        self,
        slug: str,
        category: CategoryChoice,
        *,
        change_id: int,
        user,
        state: str,
        comment: str,
        publisher_q: Q | None = None,
    ) -> AssetVersionChange:
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        change = self.repo.get_change(asset, change_id)
        if change is None:
            raise ItqanError(
                error_name="change_not_found",
                message=_("Change with id {id} not found.").format(id=change_id),
                status_code=404,
            )
        self._require_assigned(user, asset, change_language(change))

        if state == "unreviewed":
            AssetVersionChangeReview.objects.filter(change=change).delete()
            change.refresh_from_db()
            return change

        if state not in (ReviewStateChoice.APPROVED, ReviewStateChoice.COMMENTED):
            raise ItqanError(
                error_name="invalid_review_state",
                message=_("Invalid review state."),
                status_code=400,
            )
        comment = (comment or "").strip()
        if state == ReviewStateChoice.COMMENTED and not comment:
            raise ItqanError(
                error_name="review_comment_required",
                message=_("A comment is required when requesting changes."),
                status_code=400,
            )
        AssetVersionChangeReview.objects.update_or_create(
            change=change,
            defaults={
                "state": state,
                "comment": comment if state == ReviewStateChoice.COMMENTED else "",
                "reviewed_by": user,
                "reviewed_at": timezone.now(),
            },
        )
        change.refresh_from_db()
        return change
