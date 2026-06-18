import logging
from typing import Annotated, Literal

from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.models import AssetAccessRequest
from apps.content.repositories.access_request import AssetAccessRequestRepository
from apps.content.services.asset_access import AssetAccessRequestService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.ASSETS])
logger = logging.getLogger(__name__)


def _actor_label(user) -> str:
    return (user.name or "").strip() or user.email


class DeveloperOut(Schema):
    id: int
    name: str
    email: str


class AssetRefOut(Schema):
    id: int
    name: str
    publisher_id: int


class AccessRequestListOut(Schema):
    id: int
    status: str
    developer: DeveloperOut
    asset: AssetRefOut
    intended_use: str
    developer_access_reason: str
    created_at: AwareDatetime

    @staticmethod
    def resolve_developer(obj):
        return obj.developer_user

    @staticmethod
    def resolve_asset(obj):
        return obj.asset


def _resolve_approved_by(obj) -> str | None:
    if obj.approved_by_id:
        return _actor_label(obj.approved_by)
    if obj.status == AssetAccessRequest.StatusChoice.APPROVED:
        return "System"
    return None


def _resolve_rejected_by(obj) -> str | None:
    return _actor_label(obj.rejected_by) if obj.rejected_by_id else None


class AccessRequestDetailOut(AccessRequestListOut):
    approved_at: AwareDatetime | None = None
    approved_by: str | None = None
    rejected_at: AwareDatetime | None = None
    rejected_by: str | None = None
    rejection_reason: str | None = None

    @staticmethod
    def resolve_approved_by(obj) -> str | None:
        return _resolve_approved_by(obj)

    @staticmethod
    def resolve_rejected_by(obj) -> str | None:
        return _resolve_rejected_by(obj)


class AccessRequestFilter(FilterSchema):
    status: Annotated[Literal["pending", "approved", "rejected"] | None, FilterLookup(q="status")] = None
    publisher_id: Annotated[int | None, FilterLookup(q="asset__publisher_id")] = None


class RejectIn(Schema):
    rejection_reason: str


def _get_service() -> AssetAccessRequestService:
    return AssetAccessRequestService(AssetAccessRequestRepository())


@router.get("access-requests/", response=list[AccessRequestListOut])
@permission_required([permission_class(PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)])
@paginate
@ordering(ordering_fields=["created_at", "id"])
@searching(search_fields=["developer_user__name", "developer_user__email", "asset__name"])
def list_access_requests(request: Request, filters: AccessRequestFilter = Query(...)):
    qs = _get_service().list_requests(request.user)
    return filters.filter(qs)


@router.get(
    "access-requests/{int:request_id}/",
    response={200: AccessRequestDetailOut, 404: NinjaErrorResponse[Literal["not_found"]]},
)
@permission_required([permission_class(PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)])
def get_access_request(request: Request, request_id: int):
    return _get_service().get_for_user(request.user, request_id)


@router.post(
    "access-requests/{int:request_id}/accept/",
    response={
        200: AccessRequestDetailOut,
        403: NinjaErrorResponse,
        404: NinjaErrorResponse[Literal["not_found"]],
        409: NinjaErrorResponse[Literal["invalid_status"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_ACCEPT_OR_REJECT_ACCESS_REQUESTS)])
def accept_access_request(request: Request, request_id: int):
    req = _get_service().accept(request.user, request_id)
    logger.info(f"Access request accepted [request_id={request_id}, user_id={request.user.id}]")
    return req


@router.post(
    "access-requests/{int:request_id}/reject/",
    response={
        200: AccessRequestDetailOut,
        403: NinjaErrorResponse,
        404: NinjaErrorResponse[Literal["not_found"]],
        409: NinjaErrorResponse[Literal["invalid_status"]],
        422: NinjaErrorResponse[Literal["validation_error"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_ACCEPT_OR_REJECT_ACCESS_REQUESTS)])
def reject_access_request(request: Request, request_id: int, data: RejectIn):
    req = _get_service().reject(request.user, request_id, data.rejection_reason)
    logger.info(f"Access request rejected [request_id={request_id}, user_id={request.user.id}]")
    return req


class AccessRequestsSettingsOut(Schema):
    publisher_id: int
    auto_accept_access_requests: bool


class AccessRequestsSettingsIn(Schema):
    auto_accept_access_requests: bool


@router.get(
    "publishers/{int:publisher_id}/access-requests-settings/",
    response={200: AccessRequestsSettingsOut, 403: NinjaErrorResponse, 404: NinjaErrorResponse},
)
@permission_required([permission_class(PermissionChoice.PORTAL_VIEW_ACCESS_REQUESTS)])
def get_access_requests_settings(request: Request, publisher_id: int):
    return _get_service().get_settings(request.user, publisher_id)


@router.put(
    "publishers/{int:publisher_id}/access-requests-settings/",
    response={200: AccessRequestsSettingsOut, 403: NinjaErrorResponse, 404: NinjaErrorResponse},
)
@permission_required([permission_class(PermissionChoice.PORTAL_MANAGE_ACCESS_REQUESTS_SETTINGS)])
def set_access_requests_settings(request: Request, publisher_id: int, data: AccessRequestsSettingsIn):
    logger.info(
        f"Access requests settings updated [publisher_id={publisher_id}, user_id={request.user.id}, "
        f"value={data.auto_accept_access_requests}]"
    )
    return _get_service().set_auto_accept(request.user, publisher_id, data.auto_accept_access_requests)
