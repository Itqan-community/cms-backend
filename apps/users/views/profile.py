from django.http import HttpRequest


from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from ._schemas import UserProfileSchema, UserUpdateSchema
from ...core.ninja_utils.request import Request

router = ItqanRouter(tags=[NinjaTag.USERS])


@router.get(
    "auth/profile/",
    response=UserProfileSchema,
    summary="Get user profile",
    description="Get authenticated user's profile information"
)
def get_user_profile(request: Request):
    """Get authenticated user's profile"""
    user = request.user
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "phone": str(user.phone) if user.phone else None,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


@router.put(
    "auth/profile/",
    response=UserProfileSchema,
    summary="Update user profile",
    description="Update authenticated user's profile information"
)
def update_user_profile(request: HttpRequest, profile_data: UserUpdateSchema):
    """Update authenticated user's profile"""
    user = request.auth  # JWT auth provides the user
    
    # Update allowed fields
    if profile_data.name is not None:
        user.name = profile_data.name
    if profile_data.phone is not None:
        user.phone = profile_data.phone
    
    user.save()
    
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "phone": str(user.phone) if user.phone else None,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }
