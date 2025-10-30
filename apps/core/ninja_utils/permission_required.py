from collections.abc import Callable, Iterable
from functools import partial, wraps
from typing import Any

from django.http import HttpRequest
from ninja import Schema
from ninja.operation import Operation
from ninja.utils import contribute_operation_callback
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, OperationHolderMixin

from apps.core.ninja_utils.errors import NinjaErrorResponse

__all__ = ["permission_required"]


def _get_permissions(permission_classes) -> Iterable[BasePermission]:
    """
    Instantiates and returns the list of permissions that this view requires.
    """

    for permission_class in permission_classes:
        if isinstance(permission_class, (type, OperationHolderMixin)):
            permission_instance = permission_class()  # type: ignore[operator]
        else:
            permission_instance = permission_class
        yield permission_instance


def permission_denied(permission: BasePermission) -> None:
    message = getattr(permission, "message", None)
    raise PermissionDenied(message)


def check_permissions(request, view) -> None:
    """
    Check if the request should be permitted.
    Raises an appropriate exception if the request is not permitted.
    """
    permission_classes: Iterable[type[BasePermission | OperationHolderMixin]] = (
        view.permission_classes
    )
    for permission in _get_permissions(permission_classes):
        if not permission.has_permission(request=request, view=view):
            permission_denied(permission)


def permission_required(
    permission_classes: None | Iterable[type[BasePermission | OperationHolderMixin]] = None,
) -> Callable:
    """
    @api.get(...
    @permission_required([IsAuthenticated])
    def my_view(request):

    """

    if permission_classes is None:
        permission_classes = []

    def wrapper(func):
        func.permission_classes = permission_classes

        return _inject_permission_check(func)

    return wrapper


def _inject_permission_check(view: Callable) -> Callable:
    @wraps(view)
    def view_with_permission(request: HttpRequest, **kwargs: Any) -> Any:
        if not hasattr(view, "permission_classes"):
            return view(request, **kwargs)
        check_permissions(request, view)

        result = view(request, **kwargs)

        return result

    contribute_operation_callback(
        view_with_permission, partial(add_error_response_schema, 403, NinjaErrorResponse)
    )

    return view_with_permission


def add_error_response_schema(
    status_code: int, response_schema: type[Schema], op: Operation
) -> None:
    """
    Add a response schema to the operation
    takes the status code and the response schema for the error
    """

    response = op._create_response_model(response_schema)

    # add the response to the operation
    op.response_models[status_code] = response
