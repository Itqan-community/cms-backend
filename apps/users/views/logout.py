from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.ninja_utils.errors import ItqanError
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from ._schemas import RefreshTokenSchema

router = ItqanRouter(tags=[NinjaTag.AUTH])


@router.post(
    "auth/logout/",
    description="Logout user and blacklist refresh token"
)
def logout_user(request: Request, logout_data: RefreshTokenSchema = None):
    """Logout user and blacklist tokens"""
    # If refresh token is provided, blacklist it
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
        except Exception as e:
            raise ItqanError(
                error_name="blacklist_failed",
                message=f"Failed to blacklist token: {str(e)}",
                status_code=500
            )
    
    return {"message": "Successfully logged out"}
