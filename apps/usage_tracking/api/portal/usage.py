"""Portal endpoints for publisher-facing API usage dashboards."""

from __future__ import annotations

from ninja import Schema

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.USAGE])


class BoardUrlOut(Schema):
    board_url: str | None


@router.get(
    "usage/board-url/",
    response=BoardUrlOut,
    description="Get the Mixpanel board URL for the publisher in the request (X-Tenant header)",
)
def get_usage_board_url(request: Request) -> BoardUrlOut:
    publisher = request.publisher
    return BoardUrlOut(board_url=publisher.mixpanel_board_url if publisher else None)
