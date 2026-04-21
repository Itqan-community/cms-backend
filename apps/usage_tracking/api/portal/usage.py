"""Portal endpoints for publisher-facing API usage dashboards."""

from __future__ import annotations

from django.conf import settings
from ninja import Schema

from apps.core.ninja_utils.errors import ItqanError
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import PublisherMember

router = ItqanRouter(tags=[NinjaTag.USAGE])


class BoardUrlOut(Schema):
    board_url: str | None


@router.get("usage/board-url/", auth=None, response=BoardUrlOut, description="Get the Mixpanel board URL for the current user")
def get_usage_board_url(request: Request) -> BoardUrlOut:
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise ItqanError("authentication_required", "Authentication required", status_code=401)

    if user.is_staff:
        return BoardUrlOut(board_url=settings.MIXPANEL_MAIN_BOARD_URL or None)

    membership = (
        PublisherMember.objects.filter(user=user).select_related("publisher").first()
    )
    if membership is None:
        raise ItqanError("no_publisher_membership", "No publisher membership", status_code=403)

    return BoardUrlOut(board_url=membership.publisher.mixpanel_board_url or None)
