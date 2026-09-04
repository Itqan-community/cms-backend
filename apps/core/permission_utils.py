from rest_framework import exceptions, permissions

from apps.users.models import User


def permission_class(permission_code_name) -> type[permissions.BasePermission]:
    class CustomPermission(permissions.BasePermission):
        def has_permission(self, request, view):
            return check_permission(request.user, permission_code_name)

    CustomPermission.permission_code_name = permission_code_name

    # Give the generated class a readable name. NOTE: do NOT implement this by
    # assigning __repr__ on CustomPermission.__class__ — that is the shared
    # BasePermission metaclass, so it would override the repr of every DRF
    # permission class in the process (see issue #456). Renaming the class
    # itself keeps the default type repr, which renders __name__.
    CustomPermission.__name__ = f"Permission({permission_code_name})"
    CustomPermission.__qualname__ = CustomPermission.__name__

    return CustomPermission


def check_permission(user: User, permission: str, raise_exception: bool = False) -> bool:
    if not (user and user.is_authenticated and user.is_active):
        return False

    is_granted = user.has_perm(permission)

    if raise_exception and not is_granted:
        raise exceptions.PermissionDenied
    return is_granted
