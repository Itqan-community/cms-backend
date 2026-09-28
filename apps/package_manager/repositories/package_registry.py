from __future__ import annotations

from django.db.models import QuerySet

from apps.content.models import Asset, AssetVersion, Distribution, VersionStateChoice


class PackageRegistryRepository:
    """Data-access layer for package-registry queries.

    Reads only. All SemVer validity checks, collision detection and
    constraint matching are business logic and live in the service layer.
    """

    def get_asset_by_slug(self, slug: str) -> Asset | None:
        return (
            Asset.objects.select_related("publisher")
            .filter(
                slug=slug,
                restricted_for_tenant=False,
            )
            .first()
        )

    def get_eligible_package_versions(self, asset: Asset) -> QuerySet[AssetVersion]:
        return (
            AssetVersion.objects.filter(
                asset=asset,
                state=VersionStateChoice.PUBLISHED,
            )
            .filter(distributions__channel=Distribution.ChannelChoice.PACKAGE)
            .select_related("asset")
            .order_by("-created_at")
        )
