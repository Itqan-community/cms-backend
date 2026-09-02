from typing import Literal

from ninja import Field, Query, Schema

from apps.content.models import Asset
from apps.content.services.asset_access import enforce_asset_access_on_public_api
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.package_manager.services.package_registry import PackageRegistryService, ResolvedPackage
from apps.usage_tracking.decorators.track_usage import track_extra, track_usage

router = ItqanRouter(tags=[NinjaTag.PACKAGES])


class PackageVersionOut(Schema):
    slug: str
    asset_version_id: int
    resolved_version: str
    asset_name: str
    publisher_id: int | None = None
    publisher_name: str | None = None
    download_url: str | None = None


class PackageSingleOut(Schema):
    result: PackageVersionOut


class PackageManifestEntryIn(Schema):
    assets: dict[str, str] = Field(..., max_length=100)


class PackageManifestOut(Schema):
    results: list[PackageVersionOut]


def _resolve_package_to_schema(result: ResolvedPackage) -> PackageVersionOut:
    file_url = result.asset_version.file_url
    return PackageVersionOut(
        slug=result.asset.slug,
        asset_version_id=result.asset_version.pk,
        resolved_version=result.canonical_version,
        asset_name=result.asset.name,
        publisher_id=result.asset.publisher_id,
        publisher_name=result.asset.publisher.name if result.asset.publisher_id else None,
        download_url=file_url.url if file_url else None,
    )


@router.post(
    "packages/resolve/manifest/",
    response={
        200: PackageManifestOut,
        401: NinjaErrorResponse[Literal["authentication_required"]],
        403: NinjaErrorResponse[Literal["access_denied"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
        422: NinjaErrorResponse[Literal["invalid_version_constraint"]]
        | NinjaErrorResponse[Literal["no_eligible_package_versions"]]
        | NinjaErrorResponse[Literal["unsatisfiable_version_constraint"]]
        | NinjaErrorResponse[Literal["canonical_version_collision"]],
    },
)
@track_usage(entity_type="package")
def resolve_package_manifest(request: Request, body: PackageManifestEntryIn):
    service = PackageRegistryService()

    # Access check BEFORE any version resolution — iterate every slug, look up
    # the Asset, enforce access, and collect the pre-fetched objects so that
    # resolve_manifest can reuse them without a second query per slug.
    pre_fetched_assets: dict[str, Asset] = {}
    user = getattr(request, "user", None)
    for slug in body.assets:
        asset = service.find_asset(slug)
        enforce_asset_access_on_public_api(user, asset)
        pre_fetched_assets[slug] = asset

    results = service.resolve_manifest(body.assets, assets=pre_fetched_assets)

    entity_ids: list[int] = []
    entity_names: list[str] = []
    publisher_ids: list[int] = []
    publisher_names: list[str] = []
    seen_publishers: set[int] = set()
    for r in results:
        entity_ids.append(r.asset.id)
        entity_names.append(r.asset.name)
        pub_id = r.asset.publisher_id
        if pub_id is not None and pub_id not in seen_publishers:
            seen_publishers.add(pub_id)
            publisher_ids.append(pub_id)
            publisher_names.append(r.asset.publisher.name)

    track_extra(
        request,
        entity_ids=entity_ids,
        entity_names=entity_names,
        publisher_ids=publisher_ids,
        publisher_names=publisher_names,
    )
    return 200, PackageManifestOut(results=[_resolve_package_to_schema(r) for r in results])


@router.get(
    "packages/resolve/{slug}/",
    response={
        200: PackageSingleOut,
        401: NinjaErrorResponse[Literal["authentication_required"]],
        403: NinjaErrorResponse[Literal["access_denied"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
        422: NinjaErrorResponse[Literal["invalid_version_constraint"]]
        | NinjaErrorResponse[Literal["no_eligible_package_versions"]]
        | NinjaErrorResponse[Literal["unsatisfiable_version_constraint"]]
        | NinjaErrorResponse[Literal["canonical_version_collision"]],
    },
)
@track_usage(entity_type="package")
def resolve_package_single(
    request: Request,
    slug: str,
    version: str = Query(..., description="SemVer constraint or exact pin (e.g. '^1.2.0', '2.4.1')"),
):
    service = PackageRegistryService()

    asset = service.find_asset(slug)
    enforce_asset_access_on_public_api(getattr(request, "user", None), asset)
    result = service.resolve_single(slug, version, asset=asset)

    track_extra(
        request,
        entity_ids=[result.asset.id],
        entity_names=[result.asset.name],
        publisher_ids=[result.asset.publisher_id] if result.asset.publisher_id else [],
        publisher_names=[result.asset.publisher.name] if result.asset.publisher_id else [],
    )

    return 200, PackageSingleOut(result=_resolve_package_to_schema(result))
