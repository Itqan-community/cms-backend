from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.api.portal.asset_content import _CATEGORY_CONFIG
from apps.content.models import AssetVersionChange, AssetVersionChangeReview, CategoryChoice
from apps.content.services.asset_review import AssetReviewService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])


def _review_of(obj: AssetVersionChange) -> AssetVersionChangeReview | None:
    """The change's review, or None when unreviewed (reverse one-to-one may be absent)."""
    try:
        return obj.review
    except AssetVersionChangeReview.DoesNotExist:
        return None


def _resolve_review(category: str, request: Request) -> CategoryChoice:
    """Resolve the category segment (translations/tafsirs only) and enforce the
    single review permission. Review uses one permission, not the per-category ones."""
    config = _CATEGORY_CONFIG.get(category)
    if config is None:
        raise ItqanError(
            error_name="unsupported_content_category",
            message=_("Unsupported content category: {category}").format(category=category),
            status_code=404,
        )
    check_permission(request.user, PermissionChoice.PORTAL_REVIEW_CONTENT, raise_exception=True)
    return config[0]


class ReviewChangeOut(Schema):
    id: int
    sura: int
    aya: int
    surah_name: str
    change_type: str
    old_text: str
    new_text: str
    baseline_text: str
    commit_ref: str
    commit_id: int
    review_state: str
    comment: str
    reviewed_by: str | None
    reviewed_at: AwareDatetime | None

    @staticmethod
    def resolve_sura(obj: AssetVersionChange) -> int:
        return obj.ayah.sura_id

    @staticmethod
    def resolve_aya(obj: AssetVersionChange) -> int:
        return obj.ayah.number_in_sura

    @staticmethod
    def resolve_surah_name(obj: AssetVersionChange) -> str:
        return obj.ayah.sura.name

    @staticmethod
    def resolve_baseline_text(obj: AssetVersionChange) -> str:
        # The last-approved text for this ayah (annotated by the repository);
        # empty when the ayah has never been approved.
        return getattr(obj, "baseline_text", None) or ""

    @staticmethod
    def resolve_commit_ref(obj: AssetVersionChange) -> str:
        return obj.version.name

    @staticmethod
    def resolve_commit_id(obj: AssetVersionChange) -> int:
        return obj.version_id

    @staticmethod
    def resolve_review_state(obj: AssetVersionChange) -> str:
        review = _review_of(obj)
        return review.state if review is not None else "unreviewed"

    @staticmethod
    def resolve_comment(obj: AssetVersionChange) -> str:
        review = _review_of(obj)
        return review.comment if review is not None else ""

    @staticmethod
    def resolve_reviewed_by(obj: AssetVersionChange) -> str | None:
        review = _review_of(obj)
        return review.reviewed_by.name if review is not None and review.reviewed_by_id else None

    @staticmethod
    def resolve_reviewed_at(obj: AssetVersionChange):
        review = _review_of(obj)
        return review.reviewed_at if review is not None else None


class ReviewStateIn(Schema):
    state: Literal["approved", "commented", "unreviewed"]
    comment: str = ""


_REVIEW_ERRORS = (
    NinjaErrorResponse[Literal["translation_not_found"]]
    | NinjaErrorResponse[Literal["tafsir_not_found"]]
    | NinjaErrorResponse[Literal["unsupported_content_category"]]
    | NinjaErrorResponse[Literal["language_not_assigned"]]
)


@router.get(
    "content/{category}/{slug}/review/languages/",
    response={200: list[str], 404: _REVIEW_ERRORS},
)
def list_review_languages(request: Request, category: str, slug: str) -> list[str]:
    resolved = _resolve_review(category, request)
    return AssetReviewService().list_review_languages(
        slug, resolved, user=request.user, publisher_q=request.publisher_q()
    )


@router.get(
    "content/{category}/{slug}/review/changes/",
    response={200: list[ReviewChangeOut], 404: _REVIEW_ERRORS},
)
@paginate
def list_review_changes(request: Request, category: str, slug: str, language: str, state: str | None = None):
    resolved = _resolve_review(category, request)
    return AssetReviewService().list_changes(
        slug, resolved, language=language, user=request.user, state=state, publisher_q=request.publisher_q()
    )


@router.patch(
    "content/{category}/{slug}/review/changes/{change_id}/",
    response={
        200: ReviewChangeOut,
        400: NinjaErrorResponse[Literal["review_comment_required"]]
        | NinjaErrorResponse[Literal["invalid_review_state"]],
        404: _REVIEW_ERRORS | NinjaErrorResponse[Literal["change_not_found"]],
    },
)
def set_review_state(
    request: Request, category: str, slug: str, change_id: int, data: ReviewStateIn
) -> AssetVersionChange:
    resolved = _resolve_review(category, request)
    return AssetReviewService().set_review_state(
        slug,
        resolved,
        change_id=change_id,
        user=request.user,
        state=data.state,
        comment=data.comment,
        publisher_q=request.publisher_q(),
    )
