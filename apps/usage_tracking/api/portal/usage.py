"""Portal endpoints for publisher-facing API usage dashboards."""

from __future__ import annotations

from django.conf import settings
from ninja import Schema

from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.USAGE])


class BoardUrlOut(Schema):
    board_url: str | None


@router.get(
    "usage/board-url/",
    auth=ninja_jwt_auth,
    response=BoardUrlOut,
    description="Get the Mixpanel board URL for the current user",
)
def get_usage_board_url(request: Request) -> BoardUrlOut:
    return BoardUrlOut(board_url=getattr(settings, "MIXPANEL_MAIN_BOARD_URL", None) or None)
