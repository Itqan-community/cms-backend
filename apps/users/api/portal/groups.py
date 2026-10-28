import logging
from typing import Literal

from django.contrib.auth.models import Group
from django.db.models import F
from django.utils.translation import gettext_lazy as _
from ninja import Field, FilterSchema, Query, Schema
from ninja.pagination import paginate

from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PERMISSION_GROUPS, PermissionChoice
from apps.core.services.permissions import PermissionHierarchyService
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


def _publisher_group(obj: Group):
    # Portal endpoints only ever see publisher roles, which always carry a PublisherGroup.
    return obj.publisher_group


def _permission_out(codename: str) -> dict[str, str]:
    """A permission with its name in the request's language (Accept-Language)."""
    return {"code_name": codename, "name": str(PermissionChoice(codename).label)}


# --- Schemas ---


class PermissionOut(Schema):
    code_name: str
    name: str


class GroupListOut(Schema):
    id: int
    # ``name`` is the role's name in the request's language; ``name_en`` / ``name_ar`` are both,
    # for editing.
    name: str
    name_en: str
    name_ar: str

    @staticmethod
    def resolve_name(obj: Group) -> str:
        return _publisher_group(obj).name

    @staticmethod
    def resolve_name_en(obj: Group) -> str:
        return _publisher_group(obj).name_en

    @staticmethod
    def resolve_name_ar(obj: Group) -> str:
        return _publisher_group(obj).name_ar


class GroupDetailOut(GroupListOut):
    permissions: list[PermissionOut]

    @staticmethod
    def resolve_permissions(obj: Group) -> list[dict[str, str]]:
        codenames = sorted(perm.codename for perm in obj.permissions.all() if perm.codename in _PORTAL_CODENAMES)
        return [_permission_out(codename) for codename in codenames]


_PORTAL_CODENAMES = frozenset(PermissionChoice.values)  # type: ignore[attr-defined]


class GroupNamesIn(Schema):
    name_en: str
    name_ar: str


class GroupPermissionsIn(Schema):
    permissions: list[str]


# --- Permissions catalogue ---


class CataloguePermissionOut(PermissionOut):
    # Every permission this one brings with it (transitively), so the editor can show them as
    # included when it is selected.
    implies: list[str]


class PermissionGroupOut(Schema):
    key: str
    name: str
    permissions: list[CataloguePermissionOut]


@router.get("groups/permissions/", response=list[PermissionGroupOut])
@permission_required([permission_class(PermissionChoice.PORTAL_READ_GROUP)])
def list_permissions(request: Request) -> list[dict]:
    """Every permission a role can hold, grouped by usage and named in the request's language."""
    hierarchy = PermissionHierarchyService()
    return [
        {
            "key": key,
            "name": str(name),
            "permissions": [
                {
                    **_permission_out(choice.value),
                    "implies": sorted(p.value for p in hierarchy.with_implied([choice]) if p != choice),
                }
                for choice in choices
            ],
        }
        for key, name, choices in PERMISSION_GROUPS
    ]


# --- Create ---


@router.post(
    "groups/",
    response={201: GroupDetailOut, 400: NinjaErrorResponse[Literal["tenant_required", "group_already_exists"]]},
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_GROUP)])
def create_group(request: Request, data: GroupNamesIn) -> tuple[int, Group]:
    logger.info(f"Creating group [user_id={request.user.id}]")
    group = _service().create(_publisher_id(request), name_en=data.name_en, name_ar=data.name_ar)
    logger.info(f"Group created [group_id={group.id}, user_id={request.user.id}]")
    return 201, group


# --- List ---


class GroupFilter(FilterSchema):
    # Matches the role's English or Arabic name.
    name: str | None = Field(None, q=["publisher_group__name_en__icontains", "publisher_group__name_ar__icontains"])


@router.get("groups/", response={200: list[GroupListOut], 400: NinjaErrorResponse[Literal["tenant_required"]]})
@permission_required([permission_class(PermissionChoice.PORTAL_READ_GROUP)])
@paginate
@ordering(ordering_fields=["name_en", "name_ar", "id"])
@searching(search_fields=["publisher_group__name_en", "publisher_group__name_ar"])
def list_groups(request: Request, filters: GroupFilter = Query(...)):
    # Only this publisher's roles; global groups such as Itqan Internal are never offered.
    qs = (
        _service()
        .assignable_groups_qs(_publisher_id(request))
        .annotate(name_en=F("publisher_group__name_en"), name_ar=F("publisher_group__name_ar"))
    )
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
            message=_("Role with id {id} not found.").format(id=group_id),
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
def update_group(request: Request, group_id: int, data: GroupNamesIn) -> Group:
    logger.info(f"Renaming group [group_id={group_id}, user_id={request.user.id}]")
    group = _service().rename(group_id, _publisher_id(request), name_en=data.name_en, name_ar=data.name_ar)
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
