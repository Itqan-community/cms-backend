from typing import Literal

from django.conf import settings
from ninja import Schema
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.users.models import User

router = ItqanRouter(tags=[NinjaTag.AUTH])


class RefreshTokenIn(Schema):
    refresh: str


class RefreshTokenOut(Schema):
    access: str
    refresh: str | None = None


@router.post(
    "auth/token/refresh/",
    auth=None,
    response={
        200: RefreshTokenOut,
        401: NinjaErrorResponse[Literal["invalid_refresh_token"], Literal[None]]
        | NinjaErrorResponse[Literal["user_not_found"], Literal[None]],
        400: NinjaErrorResponse[Literal["token_rotation_failed"], Literal[None]],
    },
    summary="Refresh JWT access token",
    description="Refresh expired JWT access token using refresh token. Returns new access token and optionally a new refresh token if rotation is enabled.",
)
def refresh_token(request: Request, refresh_data: RefreshTokenIn):
    """Refresh JWT access token"""
    try:
        # Use rest_framework_simplejwt to refresh token
        refresh = RefreshToken(refresh_data.refresh)
        access = refresh.access_token

        response_data = {"access": str(access), "refresh": None}

        # If rotation is enabled, return new refresh token
        if getattr(settings, "SIMPLE_JWT", {}).get("ROTATE_REFRESH_TOKENS", False):
            try:
                refresh.blacklist()
                # Get user from token payload
                user_id = refresh.payload.get("user_id")
                user = User.objects.get(id=user_id)
                new_refresh = RefreshToken.for_user(user)
                response_data["refresh"] = str(new_refresh)
            except Exception as e:
                raise ItqanError(
                    error_name="token_rotation_failed",
                    message=f"Failed to rotate refresh token: {str(e)}",
                    status_code=400,
                )

        return response_data
    except (InvalidToken, TokenError):
        raise ItqanError(
            error_name="invalid_refresh_token",
            message="Invalid or expired refresh token",
            status_code=401,
        )
    except User.DoesNotExist:
        raise ItqanError(
            error_name="user_not_found",
            message="User associated with token not found",
            status_code=401,
        )
