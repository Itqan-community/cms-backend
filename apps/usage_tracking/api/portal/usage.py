"""Portal endpoints for publisher-facing API usage dashboards."""

from __future__ import annotations

from django.conf import settings
from ninja import Schema

from apps.core.ninja_utils.auth import ninja_jwt_auth_optional
from apps.core.ninja_utils.errors import ItqanError
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher, PublisherMember

router = ItqanRouter(tags=[NinjaTag.USAGE])


class BoardUrlOut(Schema):
    board_url: str | None


@router.get("usage/board-url/", auth=ninja_jwt_auth_optional, response=BoardUrlOut, description="Get the Mixpanel board URL for the current user")
def get_usage_board_url(request: Request, publisher_id: int | None = None) -> BoardUrlOut:
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise ItqanError("authentication_required", "Authentication required", status_code=401)

    if user.is_staff:
        if publisher_id is not None:
            publisher = Publisher.objects.filter(pk=publisher_id).first()
            if publisher is None:
                raise ItqanError("publisher_not_found", "Publisher not found", status_code=404)
            return BoardUrlOut(board_url=publisher.mixpanel_board_url or None)
        return BoardUrlOut(board_url=settings.MIXPANEL_MAIN_BOARD_URL or None)

    membership = PublisherMember.objects.filter(user=user).select_related("publisher").first()
    if membership is None:
        raise ItqanError("no_publisher_membership", "No publisher membership", status_code=403)

    return BoardUrlOut(board_url=membership.publisher.mixpanel_board_url or None)
