from rest_framework import exceptions, permissions

from apps.users.models import User


def permission_class(permission_code_name) -> type[permissions.BasePermission]:
    class CustomPermission(permissions.BasePermission):
        def has_permission(self, request, view):
            return check_permission(request.user, permission_code_name)

    CustomPermission.permission_code_name = permission_code_name

    # Rename the class itself instead of patching __repr__ on its metaclass.
    # CustomPermission.__class__ is DRF's BasePermissionMetaclass, which is shared by
    # every permission class in the process (including DRF's built-ins), so mutating
    # it leaks the last-created permission's label onto all of them.
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
