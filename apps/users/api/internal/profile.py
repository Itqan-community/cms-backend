from ninja import Schema
from pydantic import AwareDatetime

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permissions import PermissionChoice
from apps.users.models import Developer

_PERMISSION_CODENAMES: set[str] = set(PermissionChoice.values)

router = ItqanRouter(tags=[NinjaTag.USERS])


class PermissionSchema(Schema):
    code_name: str
    name: str


class UserProfileSchema(Schema):
    id: str
    email: str
    name: str
    phone: str | None = None
    is_active: bool
    is_profile_completed: bool
    bio: str = ""
    project_summary: str = ""
    project_url: str = ""
    job_title: str = ""
    created_at: AwareDatetime
    updated_at: AwareDatetime
    permissions: list[PermissionSchema] = []

    class Config:
        from_attributes = True


def _get_user_permissions(user):
    permissions = []
    for perm_code in user.get_all_permissions():
        code_name = perm_code.split(".")[-1]
        if code_name in _PERMISSION_CODENAMES:
            perm_choice = PermissionChoice(code_name)
            permissions.append(
                {
                    "code_name": code_name,
                    "name": str(perm_choice.label),
                }
            )
    return permissions


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
        "is_profile_completed": (user.developer_profile.profile_completed if user.developer_profile else False),
        "bio": user_developer_profile.bio if user_developer_profile else "",
        "project_summary": user_developer_profile.project_summary if user_developer_profile else "",
        "project_url": user_developer_profile.project_url if user_developer_profile else "",
        "job_title": user_developer_profile.job_title if user_developer_profile else "",
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "permissions": _get_user_permissions(user),
    }


class UserUpdateSchema(Schema):
    bio: str = ""
    project_summary: str = ""
    project_url: str = ""


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
        "is_profile_completed": (user_developer_profile.profile_completed if user_developer_profile else False),
        "bio": user_developer_profile.bio if user_developer_profile else "",
        "project_summary": user_developer_profile.project_summary if user_developer_profile else "",
        "project_url": user_developer_profile.project_url if user_developer_profile else "",
        "job_title": user_developer_profile.job_title if user_developer_profile else "",
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "permissions": _get_user_permissions(user),
    }
