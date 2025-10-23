from ninja import Schema
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.ninja_utils.errors import ItqanError
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from ...core.ninja_utils.schemas import OkSchema
from django.utils.translation import gettext as _
router = ItqanRouter(tags=[NinjaTag.AUTH])


class LogoutIn(Schema):
    refresh: str | None = None


@router.post(
    "auth/logout/",
    response=OkSchema,
    description="Logout user and blacklist refresh token"
)
def logout_user(request: Request, logout_data: LogoutIn = None):
    """Logout user and blacklist tokens"""
    if logout_data and logout_data.refresh:
        try:
            refresh = RefreshToken(logout_data.refresh)
            refresh.blacklist()
        except (InvalidToken, TokenError) as e:
            raise ItqanError(
                error_name="invalid_refresh_token",
                message="Invalid refresh token provided for blacklisting",
                status_code=400
            )

    
    return OkSchema(message=_("Successfully logged out"))
