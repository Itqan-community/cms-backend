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
    description="Get the Mixpanel board URL for the current user",
)
def get_usage_board_url(request: Request) -> BoardUrlOut:
    return BoardUrlOut(board_url=Publisher.objects.order_by("id").first().mixpanel_board_url)
