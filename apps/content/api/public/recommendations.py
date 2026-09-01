from typing import Literal

from django.http import Http404
from django.utils.translation import gettext_lazy as _
from ninja import Schema

from apps.content.models import Asset, StatusChoice
from apps.content.services.recommendations import (
    get_personalized_asset_ids,
    get_similar_asset_ids,
    get_trending_asset_ids,
    hydrate_visible_assets_in_order,
    list_active_editorial_recommendations,
)
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.usage_tracking.decorators.track_usage import track_usage

router = ItqanRouter(tags=[NinjaTag.RECOMMENDATIONS])


class RecommendationPublisherOut(Schema):
    id: int
    name: str


class RecommendationReciterOut(Schema):
    id: int
    name: str


class RecommendationRiwayahOut(Schema):
    id: int
    name: str


class RecommendedAssetOut(Schema):
    id: int
    name: str
    slug: str
    category: str
    publisher: RecommendationPublisherOut
    reciter: RecommendationReciterOut | None = None
    riwayah: RecommendationRiwayahOut | None = None

    @staticmethod
    def resolve_publisher(obj):
        return {"id": obj.publisher_id, "name": obj.publisher.name} if obj.publisher_id else None

    @staticmethod
    def resolve_reciter(obj):
        return {"id": obj.reciter_id, "name": obj.reciter.name} if obj.reciter_id else None

    @staticmethod
    def resolve_riwayah(obj):
        return {"id": obj.riwayah_id, "name": obj.riwayah.name} if obj.riwayah_id else None


@router.get(
    "recommendations/similar/{asset_id}/",
    response={
        200: list[RecommendedAssetOut],
        404: NinjaErrorResponse[Literal["not_found"]],
    },
)
@track_usage(entity_type="recommendation_similar")
def get_similar_recommendations(request: Request, asset_id: int):
    """
    "Users who liked this also liked" — assets sharing reciter/riwayah/qiraah/category
    with `asset_id`, ranked by a precomputed similarity score (see
    apps.content.services.recommendations).

    404s only when the source asset itself doesn't exist or isn't publicly visible;
    an asset with zero matches simply returns an empty list, since "no similar content
    yet" is a valid, non-error outcome.

    This is discovery metadata (asset name/reciter/publisher), not audio content, so
    unlike /recitations/{asset_id}/ it doesn't require enforce_asset_access_on_public_api
    — it's readable the same way /reciters/ or /recitations/ (the list endpoint) are.
    """
    source_exists = Asset.objects.filter(
        id=asset_id,
        status=StatusChoice.READY,
        restricted_for_tenant=False,
    ).exists()
    if not source_exists:
        raise Http404(str(_("No asset matches the given query.")))

    similar_ids = get_similar_asset_ids(asset_id)
    return hydrate_visible_assets_in_order(similar_ids)


@router.get(
    "recommendations/trending/",
    response={200: list[RecommendedAssetOut]},
)
@track_usage(entity_type="recommendation_trending")
def get_trending_recommendations(request: Request, category: str | None = None):
    """
    Currently popular content, ranked by recent usage weighted by event kind (a
    download counts for more than a view). Precomputed periodically via Celery beat
    (see apps.content.services.recommendations); an empty/not-yet-computed cache
    simply yields an empty list, same as /similar/ treats "no matches".

    `category` optionally scopes the leaderboard to one CategoryChoice value (e.g.
    "recitation"); an unrecognised value behaves like "nothing trending yet" (empty
    list) rather than a 400, since that's cheap to tell apart from a client bug by
    just looking at the response.
    """
    trending_ids = get_trending_asset_ids(category=category)
    return hydrate_visible_assets_in_order(trending_ids)


@router.get(
    "recommendations/personalized/",
    response={
        200: list[RecommendedAssetOut],
        401: NinjaErrorResponse[Literal["authentication_required"]],
    },
)
@track_usage(entity_type="recommendation_personalized")
def get_personalized_recommendations(request: Request):
    """
    Suggestions based on the authenticated user's own download/view history (see
    compute_personalized_recommendations). Falls back to global trending when the
    user has no precomputed personalized data yet -- new account, no history since the
    last nightly run, or a history too narrow to score any candidates all count as "no
    personalized data", a valid non-error outcome, not "nothing to recommend at all".

    Requires authentication (unlike similar/trending/editorial, which are pure
    discovery metadata): personalized results are tied to a specific user's history.
    """
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        raise ItqanError(
            "authentication_required",
            _("You must be signed in to get personalized recommendations."),
            status_code=401,
        )

    personalized_ids = get_personalized_asset_ids(user.id)
    if not personalized_ids:
        personalized_ids = get_trending_asset_ids()
    return hydrate_visible_assets_in_order(personalized_ids)


class EditorialRecommendationOut(Schema):
    id: int
    title: str
    description: str
    assets: list[RecommendedAssetOut]


@router.get(
    "recommendations/editorial/",
    response={200: list[EditorialRecommendationOut]},
)
@track_usage(entity_type="recommendation_editorial")
def get_editorial_recommendations(request: Request):
    """
    Admin-curated featured collections (e.g. seasonal spotlights) currently in their
    active window, newest first. Unlike similar/trending/personalized this reads
    straight from the DB -- editorial collections change rarely and the query is
    already small and indexed, so there's no precompute/cache step.
    """
    return list_active_editorial_recommendations()
