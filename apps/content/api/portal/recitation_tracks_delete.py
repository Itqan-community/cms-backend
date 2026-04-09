from typing import Literal

from rest_framework.exceptions import PermissionDenied

from apps.content.api.portal.schemas.recitation_tracks_delete import DeleteTracksIn
from apps.content.repositories.recitation_track import RecitationTrackRepository
from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


@router.delete(
    "recitation-tracks/",
    response={
        204: None,
        401: NinjaErrorResponse[Literal["authentication_error"], Literal[None]],
        403: NinjaErrorResponse[Literal["permission_denied"], Literal[None]],
    },
    auth=ninja_jwt_auth,
)
def delete_tracks(request: Request, data: DeleteTracksIn):
    if not request.user.is_staff:
        raise PermissionDenied("Staff only")

    repo = RecitationTrackRepository()
    tracks = repo.get_recitation_tracks_by_ids(data.track_ids)

    if not data.track_ids or len(tracks) != len(data.track_ids):
        raise ItqanError(
            error_name="track_not_found",
            message="Some track IDs are invalid or do not exist.",
            status_code=400,
        )

    repo.delete_recitation_tracks(tracks)
    return 204, None
