from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import Query, Schema
from ninja.pagination import paginate

from apps.content.models import Asset, CategoryChoice, RecitationSurahTrack
from apps.content.repositories.recitation_track import RecitationTrackRepository
from apps.content.services.recitation_quality_resolution import find_quality_by_token
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RecitationTrackOut(Schema):
    id: int
    surah_number: int
    audio_url: str | None
    duration_ms: int
    size_bytes: int
    filename: str | None

    @staticmethod
    def resolve_audio_url(obj: RecitationSurahTrack) -> str | None:
        if obj.audio_file:
            return obj.audio_file.url
        return None

    @staticmethod
    def resolve_filename(obj: RecitationSurahTrack) -> str | None:
        return obj.original_filename


@router.get(
    "recitations/{recitation_slug}/recitation-tracks/",
    response={
        200: list[RecitationTrackOut],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]] | NinjaErrorResponse[Literal["quality_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_RECITATION)])
@paginate
def list_tracks(request: Request, recitation_slug: str, quality: str | None = Query(None)):
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(
            category=CategoryChoice.RECITATION, slug=recitation_slug
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="asset_not_found",
            message=_("Asset with slug {slug} not found.").format(slug=recitation_slug),
            status_code=404,
        ) from exc

    # Tracks always belong to exactly one quality, so scope to the requested variant
    # or the default. `quality` accepts a slug or a name; an unresolvable value 404s
    # rather than looking like an empty quality.
    if quality is not None:
        matched = find_quality_by_token(asset.id, quality)
        if matched is None:
            raise ItqanError(
                error_name="quality_not_found",
                message=_("Quality {quality} not found.").format(quality=quality),
                status_code=404,
            )
        quality_filter = {"quality_id": matched.id}
    else:
        quality_filter = {"quality__is_default": True}

    return (
        RecitationSurahTrack.objects.filter(asset_id=asset.id, **quality_filter)
        .select_related("quality")
        .order_by("surah_number")
    )


class DeleteTracksIn(Schema):
    track_ids: list[int]


@router.delete(
    "recitation-tracks/",
    response={
        204: None,
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_RECITATION)])
def delete_tracks(request: Request, data: DeleteTracksIn):
    repo = RecitationTrackRepository()
    tracks = repo.get_recitation_tracks_by_ids(data.track_ids, publisher_q=request.publisher_q("asset__publisher"))

    if not data.track_ids or len(tracks) != len(data.track_ids):
        raise ItqanError(
            error_name="track_not_found",
            message=_("Some track IDs are invalid or do not exist."),
            status_code=400,
        )

    repo.delete_recitation_tracks(tracks)
    return 204, None
