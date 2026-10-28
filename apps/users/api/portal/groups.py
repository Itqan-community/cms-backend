import logging
from typing import Literal

from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate

from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice
from apps.users.repositories.group import GroupRepository
from apps.users.services.group import GroupService

router = ItqanRouter(tags=[NinjaTag.GROUPS])
logger = logging.getLogger(__name__)


def _service() -> GroupService:
    return GroupService(GroupRepository())


def _publisher_id(request: Request) -> int:
    """Groups are per-publisher roles, so every groups endpoint needs the X-Tenant publisher."""
    if request.publisher is None:
        raise ItqanError(
            error_name="tenant_required",
            message=_("Select a publisher first."),
            status_code=400,
        )
    return request.publisher.id


def _display_name(obj: Group) -> str:
    publisher_group = getattr(obj, "publisher_group", None)
    return publisher_group.name if publisher_group else obj.name


# --- Schemas ---


class GroupListOut(Schema):
    id: int
    name: str

    @staticmethod
    def resolve_name(obj: Group) -> str:
        return _display_name(obj)


class GroupDetailOut(Schema):
    id: int
    name: str
    permissions: list[str]

    @staticmethod
    def resolve_name(obj: Group) -> str:
        return _display_name(obj)

    @staticmethod
    def resolve_permissions(obj: Group) -> list[str]:
        return sorted(perm.codename for perm in obj.permissions.all())


class GroupCreateIn(Schema):
    name: str


class GroupUpdateIn(Schema):
    name: str


class GroupPermissionsIn(Schema):
    permissions: list[str]


# --- Create ---


@router.post(
    "groups/",
    response={201: GroupDetailOut, 400: NinjaErrorResponse[Literal["tenant_required", "group_already_exists"]]},
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_GROUP)])
def create_group(request: Request, data: GroupCreateIn) -> tuple[int, Group]:
    logger.info(f"Creating group [user_id={request.user.id}]")
    group = _service().create(_publisher_id(request), name=data.name)
    logger.info(f"Group created [group_id={group.id}, user_id={request.user.id}]")
    return 201, group


# --- List ---


class GroupFilter(FilterSchema):
    name: str | None = None


@router.get("groups/", response={200: list[GroupListOut], 400: NinjaErrorResponse[Literal["tenant_required"]]})
@permission_required([permission_class(PermissionChoice.PORTAL_READ_GROUP)])
@paginate
@ordering(ordering_fields=["name", "id"])
@searching(search_fields=["name"])
def list_groups(request: Request, filters: GroupFilter = Query(...)):
    # Only this publisher's roles; global groups such as Itqan Internal are never offered.
    qs = _service().assignable_groups_qs(_publisher_id(request))
    qs = filters.filter(qs)
    return qs


# --- Retrieve ---


@router.get(
    "groups/{int:group_id}/",
    response={
        200: GroupDetailOut,
        400: NinjaErrorResponse[Literal["tenant_required"]],
        404: NinjaErrorResponse[Literal["group_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_GROUP)])
def retrieve_group(request: Request, group_id: int) -> Group:
    group = (
        _service()
        .assignable_groups_qs(_publisher_id(request))
        .prefetch_related("permissions")
        .filter(id=group_id)
        .first()
    )
    if group is None:
        raise ItqanError(
            error_name="group_not_found",
            message=_("Group with id {id} not found.").format(id=group_id),
            status_code=404,
        )
    return group


# --- Update (rename) ---


@router.put(
    "groups/{int:group_id}/",
    response={
        200: GroupDetailOut,
        400: NinjaErrorResponse,
        404: NinjaErrorResponse[Literal["group_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_GROUP)])
def update_group(request: Request, group_id: int, data: GroupUpdateIn) -> Group:
    logger.info(f"Renaming group [group_id={group_id}, user_id={request.user.id}]")
    group = _service().rename(group_id, _publisher_id(request), name=data.name)
    logger.info(f"Group renamed [group_id={group_id}, user_id={request.user.id}]")
    return group


# --- Set permissions ---


@router.put(
    "groups/{int:group_id}/permissions/",
    response={
        200: GroupDetailOut,
        400: NinjaErrorResponse[Literal["invalid_permission", "permission_not_grantable", "tenant_required"]],
        404: NinjaErrorResponse[Literal["group_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_GROUP)])
def set_group_permissions(request: Request, group_id: int, data: GroupPermissionsIn) -> Group:
    """Replace the group's permissions with the submitted set (hierarchy applied)."""
    logger.info(f"Setting group permissions [group_id={group_id}, user_id={request.user.id}]")
    group = _service().set_permissions(
        group_id, _publisher_id(request), permissions=data.permissions, editor=request.user
    )
    logger.info(f"Group permissions set [group_id={group_id}, user_id={request.user.id}]")
    return group


# --- Delete ---


@router.delete(
    "groups/{int:group_id}/",
    response={
        204: None,
        400: NinjaErrorResponse[Literal["group_in_use", "tenant_required"]],
        404: NinjaErrorResponse[Literal["group_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_GROUP)])
def delete_group(request: Request, group_id: int) -> tuple[int, None]:
    logger.info(f"Deleting group [group_id={group_id}, user_id={request.user.id}]")
    _service().delete(group_id, _publisher_id(request))
    logger.info(f"Group deleted [group_id={group_id}, user_id={request.user.id}]")
    return 204, None
