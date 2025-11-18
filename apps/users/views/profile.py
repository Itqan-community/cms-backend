from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.users.models import Developer

from ...core.ninja_utils.request import Request
from ._schemas import UserProfileSchema, UserUpdateSchema

router = ItqanRouter(tags=[NinjaTag.USERS])


@router.get(
    "auth/profile/",
    response=UserProfileSchema,
    summary="Get user profile",
    description="Get authenticated user's profile information",
)
def get_user_profile(request: Request):
    """Get authenticated user's profile"""
    user = request.user
    user_developer_profile, _ = Developer.objects.get_or_create(user=user)
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "phone": str(user.phone) if user.phone else None,
        "is_active": user.is_active,
        "is_profile_completed": (
            user.developer_profile.profile_completed if user.developer_profile else False
        ),
        "bio": user_developer_profile.bio if user_developer_profile else "",
        "project_summary": user_developer_profile.project_summary if user_developer_profile else "",
        "project_url": user_developer_profile.project_url if user_developer_profile else "",
        "job_title": user_developer_profile.job_title if user_developer_profile else "",
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


@router.put(
    "auth/profile/",
    response=UserProfileSchema,
    summary="Update user profile",
    description="Update authenticated user's profile information",
)
def update_user_profile(request: Request, profile_data: UserUpdateSchema):
    """Update authenticated user's profile"""
    user = request.user
    user_developer_profile, _ = Developer.objects.get_or_create(user=user)

    # Update allowed fields
    if profile_data.bio is not None:
        user_developer_profile.bio = profile_data.bio
    if profile_data.project_summary is not None:
        user_developer_profile.project_summary = profile_data.project_summary
    if profile_data.project_url is not None:
        user_developer_profile.project_url = profile_data.project_url

    user_developer_profile.save()

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "phone": str(user.phone) if user.phone else None,
        "is_active": user.is_active,
        "is_profile_completed": (
            user_developer_profile.profile_completed if user_developer_profile else False
        ),
        "bio": user_developer_profile.bio if user_developer_profile else "",
        "project_summary": user_developer_profile.project_summary if user_developer_profile else "",
        "project_url": user_developer_profile.project_url if user_developer_profile else "",
        "job_title": user_developer_profile.job_title if user_developer_profile else "",
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }
