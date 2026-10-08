from __future__ import annotations

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetVersion,
    AssetVersionChange,
    AssetVersionEntry,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_templates import unit_spec_for


class PackageRegistryRepository:
    """Data-access layer for package-registry queries.

    All SemVer validity checks, collision detection and constraint matching
    are business logic and live in the service layer.
    """

    def get_asset_by_slug(self, slug: str) -> Asset | None:
        return (
            Asset.objects.select_related("publisher")
            .filter(
                slug=slug,
                status=StatusChoice.READY,
                restricted_for_tenant=False,
            )
            .first()
        )

    def list_installable_assets(
        self,
        *,
        open_access: bool | None = None,
        category: str | None = None,
    ) -> QuerySet[Asset]:
        """READY, unrestricted assets with at least one installable version in a
        READY language rendition, ordered by slug."""
        installable_version = AssetVersion.objects.filter(
            asset=OuterRef("pk"),
            state=VersionStateChoice.PUBLISHED,
            asset_language__status=StatusChoice.READY,
        ).filter(_has_content_q())
        qs = Asset.objects.select_related("publisher").filter(
            Exists(installable_version),
            status=StatusChoice.READY,
            restricted_for_tenant=False,
        )
        if open_access is not None:
            qs = qs.filter(is_open_access=open_access)
        if category is not None:
            qs = qs.filter(category=category)
        return qs.order_by("slug")

    def list_available_languages(self, asset: Asset) -> QuerySet[AssetLanguage]:
        """The asset's READY renditions, source language first."""
        return AssetLanguage.objects.filter(asset=asset, status=StatusChoice.READY).order_by("-is_source", "language")

    def get_available_language(self, asset: Asset, language: str | None) -> AssetLanguage | None:
        """The consumer-available (READY) rendition for ``language``, or the
        source rendition when ``language`` is None."""
        renditions = AssetLanguage.objects.filter(asset=asset, status=StatusChoice.READY)
        if language is None:
            return renditions.filter(is_source=True).first()
        return renditions.filter(language=language).first()

    def get_eligible_package_versions(self, asset_language: AssetLanguage) -> QuerySet[AssetVersion]:
        """Published versions of one language rendition that have content to
        serve: an uploaded file, or entries / stored changes to build one from."""
        return (
            AssetVersion.objects.filter(
                asset_language=asset_language,
                state=VersionStateChoice.PUBLISHED,
            )
            .filter(_has_content_q())
            .select_related("asset", "asset_language")
            .order_by("-created_at")
        )

    def get_downloadable_version(self, asset_version_id: int) -> AssetVersion | None:
        """A version the registry could have resolved: published, in a READY,
        unrestricted asset and a READY language, with content to serve."""
        return (
            AssetVersion.objects.filter(
                pk=asset_version_id,
                state=VersionStateChoice.PUBLISHED,
                asset__status=StatusChoice.READY,
                asset__restricted_for_tenant=False,
                asset_language__status=StatusChoice.READY,
            )
            .filter(_has_content_q())
            .select_related("asset", "asset__publisher", "asset_language")
            .first()
        )

    @transaction.atomic
    def store_generated_package_file(self, version: AssetVersion) -> AssetVersion | None:
        """Build a version's CSV from its content and save it as the version's file.

        Superseded versions lose their file when publishing prunes them; their
        content is rebuilt from the stored changes. Locks the row so concurrent
        downloads generate the file once. Returns None when there is no content
        to build from.
        """
        locked = (
            AssetVersion.objects.select_for_update(of=("self",))
            .select_related("asset", "asset_language")
            .get(pk=version.pk)
        )
        if locked.file_url:
            return locked
        content_repo = AssetContentRepository()
        snapshot = content_repo.reconstruct_entries(locked)
        if not any(snapshot.values()):
            return None
        content = content_repo.snapshot_to_csv_bytes(snapshot, unit_spec_for(locked.asset), asset=locked.asset)
        filename = f"{locked.asset.slug}-{locked.asset_language.language}-{locked.name}.csv".replace(" ", "_")
        locked.file_url.save(filename, ContentFile(content), save=False)
        locked.size_bytes = len(content)
        locked.save(update_fields=["file_url", "size_bytes", "updated_at"])
        return locked


def _has_content_q() -> Q:
    has_entries = Exists(AssetVersionEntry.objects.filter(version=OuterRef("pk")))
    has_changes = Exists(AssetVersionChange.objects.filter(version=OuterRef("pk")))
    has_file = Q(file_url__isnull=False) & ~Q(file_url="")
    return has_file | Q(has_entries) | Q(has_changes)
