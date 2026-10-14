from ninja import Field, Schema

from apps.content.models import AssetVersion
from apps.package_manager.services.package_registry import PackageRegistryService, PackageVersionStatus


class PackageStatusOut(Schema):
    """A version's availability in the package manager (itqan CLI), for portal version lists."""

    package_status: PackageVersionStatus = Field(
        ...,
        description="`released`: new installs may get it. `withdrawn`: the publisher rolled back past it; "
        "only lockfiles pinned to it still install it. `removed`: removed by Itqan. "
        "`not_released`: never published.",
    )
    withdrawal_reason: str = Field(..., description="The publisher's reason for rolling back past this version.")
    removal_reason: str

    @staticmethod
    def resolve_package_status(obj: AssetVersion, context: dict) -> PackageVersionStatus:
        cache = context["request"].__dict__.setdefault("_package_statuses", {})
        return PackageRegistryService().cached_status(obj, cache)
