"""Categories the package manager does not serve (recitations): resolve rejects
them and their files can't be downloaded. The catalog side is covered in
test_package_registry_catalog.py."""

from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetVersion,
    CategoryChoice,
    Qiraah,
    Reciter,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher


class NonInstallableCategoryTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher")

    def _recitation_with_version(self, slug: str, name: str = "1.0.0") -> AssetVersion:
        asset = Asset.objects.create(
            name=slug.title(),
            slug=slug,
            publisher=self.publisher,
            category=CategoryChoice.RECITATION,
            license="CC0",
            file_size="1 MB",
            format="mp3",
            description="desc",
            language="ar",
            status=StatusChoice.READY,
            reciter=baker.make(Reciter),
            qiraah=baker.make(Qiraah),
        )
        version = baker.make(
            AssetVersion,
            asset=asset,
            asset_language=asset.get_or_create_source_language(),
            name=name,
            state=VersionStateChoice.PUBLISHED,
        )
        version.file_url = SimpleUploadedFile(name=f"{slug}-{name}.csv", content=b"x")
        version.save()
        return version

    def test_resolve_single_where_asset_is_recitation_should_return_422_category_not_installable(self):
        # Arrange
        self._recitation_with_version("recitation-a")

        # Act
        response = self.client.get("/packages/resolve/recitation-a/", {"version": "^1.0.0"})

        # Assert
        self.assertEqual(422, response.status_code, response.content)
        self.assertEqual("category_not_installable", response.json()["error_name"])

    def test_resolve_manifest_where_entry_is_recitation_should_return_422_category_not_installable(self):
        # Arrange
        self._recitation_with_version("recitation-a")

        # Act
        response = self.client.post(
            "/packages/resolve/manifest/",
            {"assets": {"recitation-a": "^1.0.0"}},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(422, response.status_code, response.content)
        self.assertEqual("category_not_installable", response.json()["error_name"])

    def test_download_package_file_where_asset_is_recitation_should_return_404_version_not_found(self):
        # Arrange
        version = self._recitation_with_version("recitation-a")

        # Act
        response = self.client.get(f"/packages/download/{version.pk}/recitation-a-ar-1.0.0.csv/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])
