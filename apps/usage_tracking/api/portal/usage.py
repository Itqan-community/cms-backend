"""Portal endpoints for publisher-facing API usage dashboards."""

from __future__ import annotations

from ninja import Schema

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher

router = ItqanRouter(tags=[NinjaTag.USAGE])


class BoardUrlOut(Schema):
    board_url: str | None


@router.get(
    "usage/board-url/",
    response=BoardUrlOut,
    description=(
        "Get the Mixpanel board URL for the publisher in the request (X-Tenant header). "
        "Itqan staff may pick any publisher with `publisher_id`."
    ),
)
def get_usage_board_url(request: Request, publisher_id: int | None = None) -> BoardUrlOut:
    if publisher_id is not None and request.user.is_staff:
        publisher = Publisher.objects.filter(id=publisher_id).first()
    else:
        # X-Tenant is not checked for membership on its own; only answer for a publisher the caller may see.
        publisher = (
            Publisher.objects.filter(request.publisher_q("id")).filter(pk=request.publisher.pk).first()
            if request.publisher
            else None
        )
    return BoardUrlOut(board_url=publisher.mixpanel_board_url if publisher else None)
