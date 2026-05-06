from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import Schema
from ninja.pagination import paginate

from apps.content.models import Asset, CategoryChoice, RecitationSurahTrack
from apps.content.repositories.recitation_track import RecitationTrackRepository
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
        404: NinjaErrorResponse[Literal["asset_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_RECITATION)])
@paginate
def list_tracks(request: Request, recitation_slug: str):
    try:
        asset = Asset.objects.filter(request.user_publisher_q()).get(
            category=CategoryChoice.RECITATION, slug=recitation_slug
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="asset_not_found",
            message=_("Asset with slug {slug} not found.").format(slug=recitation_slug),
            status_code=404,
        ) from exc
    return RecitationSurahTrack.objects.filter(asset_id=asset.id).order_by("surah_number")


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
    tracks = repo.get_recitation_tracks_by_ids(
        data.track_ids, user_publisher_q=request.user_publisher_q(lookup="asset__publisher_id")
    )

    if not data.track_ids or len(tracks) != len(data.track_ids):
        raise ItqanError(
            error_name="track_not_found",
            message="Some track IDs are invalid or do not exist.",
            status_code=400,
        )

    repo.delete_recitation_tracks(tracks)
    return 204, None
