"""Itqan admins remove a version from the package manager (itqan CLI) and every
consumer surface.

Withdrawing needs no endpoint of its own: publishing an earlier version (a
rollback, with a reason) withdraws the versions after it. Each version's status
is part of the portal version lists (``PackageStatusOut``).
"""

from typing import Literal

from ninja import Schema
from pydantic import AwareDatetime, Field

from apps.content.models import AssetVersion
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission
from apps.core.permissions import PermissionChoice
from apps.package_manager.services.package_registry import PackageRegistryService, PackageVersionStatus

router = ItqanRouter(tags=[NinjaTag.PACKAGES])


class RemovedVersionOut(Schema):
    id: int
    name: str
    package_status: PackageVersionStatus
    removed_at: AwareDatetime | None = None
    removal_reason: str


class RemoveIn(Schema):
    reason: str = Field(..., min_length=1, max_length=500)


@router.post(
    "packages/versions/{version_id}/remove/",
    response={
        200: RemovedVersionOut,
        400: NinjaErrorResponse[Literal["version_already_removed"]] | NinjaErrorResponse[Literal["version_is_served"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["version_not_found"]],
    },
)
def remove_package_version(request: Request, version_id: int, data: RemoveIn):
    """Remove a version for good (Itqan admins): it is never installed or served
    again, and lockfiles pinned to it fail with ``version_removed``."""
    check_permission(request.user, PermissionChoice.PORTAL_REMOVE_PACKAGE_VERSION, raise_exception=True)
    service = PackageRegistryService()
    version = service.get_portal_version(version_id, publisher_q=request.publisher_q("asset__publisher"))
    version: AssetVersion = service.remove_version(version, user=request.user, reason=data.reason.strip())
    return RemovedVersionOut(
        id=version.pk,
        name=version.name,
        package_status=PackageVersionStatus.REMOVED,
        removed_at=version.removed_at,
        removal_reason=version.removal_reason,
    )
