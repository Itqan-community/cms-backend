from rest_framework import exceptions
from rest_framework import permissions

from apps.users.models import User


def permission_class(permission_code_name) -> type[permissions.BasePermission]:
    class CustomPermission(permissions.BasePermission):
        def has_permission(self, request, view):
            return check_permission(request.user, permission_code_name)

    CustomPermission.permission_code_name = permission_code_name

    def rep(cls):
        return f"Permission({permission_code_name})"

    CustomPermission.__class__.__repr__ = rep

    return CustomPermission


def check_permission(user: User, permission: str, raise_exception: bool = False) -> bool:
    if not (user and user.is_authenticated and user.is_active):
        return False

    is_granted = user.has_perm(permission)

    if raise_exception and not is_granted:
        raise exceptions.PermissionDenied
    return is_granted
