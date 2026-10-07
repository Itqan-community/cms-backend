from typing import Literal

from django.http import HttpResponseRedirect
from django.urls import reverse
from ninja import Field, Query, Schema
from ninja.pagination import paginate

from apps.content.models import Asset
from apps.content.services.asset_access import enforce_asset_access_on_public_api
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.package_manager.services.package_registry import PackageRegistryService, PackageRequest, ResolvedPackage
from apps.usage_tracking.decorators.track_usage import track_extra, track_usage

router = ItqanRouter(tags=[NinjaTag.PACKAGES])


class PackageVersionOut(Schema):
    name: str = Field(..., description="Manifest entry name (the slug unless the entry sets `asset`).")
    slug: str
    language: str = Field(..., description="Language code of the resolved rendition.")
    asset_version_id: int
    resolved_version: str
    asset_name: str
    publisher_id: int | None = None
    publisher_name: str | None = None
    download_url: str | None = None


class PackageLanguageOut(Schema):
    language: str
    is_source: bool
    latest_version: str = Field(..., description="Newest stable version; what a `^` constraint on it resolves to.")


class PackageCatalogOut(Schema):
    slug: str
    name: str
    category: str
    is_open_access: bool
    publisher_name: str | None = None
    languages: list[PackageLanguageOut]

    @staticmethod
    def resolve_publisher_name(obj: Asset) -> str | None:
        return obj.publisher.name if obj.publisher_id else None

    @staticmethod
    def resolve_languages(obj: Asset) -> list[PackageLanguageOut]:
        return [
            PackageLanguageOut(language=lang.language, is_source=lang.is_source, latest_version=lang.latest_version)
            for lang in PackageRegistryService().catalog_languages(obj)
        ]


class PackageSingleOut(Schema):
    result: PackageVersionOut


class PackageRequestIn(Schema):
    version: str
    asset: str | None = Field(None, description="Asset slug; defaults to the entry name.")
    language: str | None = Field(None, description="Language rendition; defaults to the asset's source language.")


class PackageManifestEntryIn(Schema):
    assets: dict[str, str | PackageRequestIn] = Field(
        ...,
        max_length=100,
        description="Entry name → version constraint, or an object to pick the asset and language explicitly.",
    )

    def to_requests(self) -> dict[str, PackageRequest]:
        requests: dict[str, PackageRequest] = {}
        for name, entry in self.assets.items():
            if isinstance(entry, str):
                requests[name] = PackageRequest(slug=name, version=entry)
            else:
                requests[name] = PackageRequest(
                    slug=entry.asset or name, version=entry.version, language=entry.language
                )
        return requests


class PackageManifestOut(Schema):
    results: list[PackageVersionOut]


def _download_url(request: Request, result: ResolvedPackage) -> str:
    """Absolute URL to fetch the version's file: the stored file when it has
    one, otherwise the download endpoint that generates it on first request."""
    version = result.asset_version
    if version.file_url:
        return request.build_absolute_uri(version.file_url.url)
    filename = f"{result.asset.slug}-{result.asset_language.language}-{version.name}.csv".replace(" ", "_")
    path = reverse(
        f"{request.resolver_match.namespace}:download_package_file",
        kwargs={"asset_version_id": version.pk, "filename": filename},
    )
    return request.build_absolute_uri(path)


def _resolve_package_to_schema(request: Request, result: ResolvedPackage) -> PackageVersionOut:
    return PackageVersionOut(
        name=result.name or result.asset.slug,
        slug=result.asset.slug,
        language=result.asset_language.language,
        asset_version_id=result.asset_version.pk,
        resolved_version=result.canonical_version,
        asset_name=result.asset.name,
        publisher_id=result.asset.publisher_id,
        publisher_name=result.asset.publisher.name if result.asset.publisher_id else None,
        download_url=_download_url(request, result),
    )


@router.get("packages/", response=list[PackageCatalogOut])
@paginate
def list_packages(
    request: Request,
    open_access: bool | None = Query(
        None, description="Only assets that need no API key (true) or only gated ones (false)."
    ),
):
    """Installable assets and their language renditions.

    Lists READY assets that have at least one version the registry can resolve,
    each with its available languages (source first) and their newest version.
    `itqan init` uses it to write a starter manifest.
    """
    return PackageRegistryService().list_installable_assets(open_access=open_access)


@router.post(
    "packages/resolve/manifest/",
    response={
        200: PackageManifestOut,
        401: NinjaErrorResponse[Literal["authentication_required"]],
        403: NinjaErrorResponse[Literal["access_denied"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]]
        | NinjaErrorResponse[Literal["language_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]],
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
    package_requests = body.to_requests()
    pre_fetched_assets: dict[str, Asset] = {}
    user = getattr(request, "user", None)
    for package_request in package_requests.values():
        if package_request.slug in pre_fetched_assets:
            continue
        asset = service.find_asset(package_request.slug)
        enforce_asset_access_on_public_api(user, asset)
        pre_fetched_assets[package_request.slug] = asset

    results = service.resolve_manifest(package_requests, assets=pre_fetched_assets)

    entity_ids: list[int] = []
    entity_names: list[str] = []
    publisher_ids: list[int] = []
    publisher_names: list[str] = []
    seen_publishers: set[int] = set()
    seen_assets: set[int] = set()
    for r in results:
        if r.asset.id in seen_assets:
            continue
        seen_assets.add(r.asset.id)
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
    return 200, PackageManifestOut(results=[_resolve_package_to_schema(request, r) for r in results])


@router.get(
    "packages/resolve/{slug}/",
    response={
        200: PackageSingleOut,
        401: NinjaErrorResponse[Literal["authentication_required"]],
        403: NinjaErrorResponse[Literal["access_denied"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]]
        | NinjaErrorResponse[Literal["language_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]],
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
    language: str | None = Query(None, description="Language rendition; defaults to the asset's source language."),
):
    service = PackageRegistryService()

    asset = service.find_asset(slug)
    enforce_asset_access_on_public_api(getattr(request, "user", None), asset)
    result = service.resolve_single(slug, version, language=language, asset=asset)

    track_extra(
        request,
        entity_ids=[result.asset.id],
        entity_names=[result.asset.name],
        publisher_ids=[result.asset.publisher_id] if result.asset.publisher_id else [],
        publisher_names=[result.asset.publisher.name] if result.asset.publisher_id else [],
    )

    return 200, PackageSingleOut(result=_resolve_package_to_schema(request, result))


@router.get(
    "packages/download/{asset_version_id}/{filename}/",
    url_name="download_package_file",
    response={
        302: None,
        401: NinjaErrorResponse[Literal["authentication_required"]],
        403: NinjaErrorResponse[Literal["access_denied"]],
        404: NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["package_content_unavailable"]],
    },
)
def download_package_file(request: Request, asset_version_id: int, filename: str):
    """Redirect to a resolved version's file, generating it on the first request.

    Superseded versions have no stored file; the first download rebuilds it as
    CSV from the version's stored changes and saves it, so later downloads are
    a plain redirect. ``filename`` only names the download for the client.
    """
    service = PackageRegistryService()
    version = service.get_downloadable_version(asset_version_id)
    enforce_asset_access_on_public_api(getattr(request, "user", None), version.asset)
    version = service.ensure_package_file(version)
    return HttpResponseRedirect(version.file_url.url)
