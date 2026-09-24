from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, AssetVersion, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class PortalFileUrlTests(BaseTestCase):
    """Portal responses carry file URLs the browser can fetch from any origin.

    Local storage yields relative /media/ paths; resolved against the frontend's
    origin they 404, so the portal must return them absolute."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="file-urls@example.com", name="Reader", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        self.publisher = baker.make(Publisher, name="Files Publisher")

    def _asset_with_file(self, category: str, slug: str) -> Asset:
        asset = baker.make(
            Asset,
            publisher=self.publisher,
            category=category,
            template=AssetTemplateChoice.AYAH if category == CategoryChoice.TAFSIR else None,
            status=StatusChoice.READY,
            slug=slug,
            language="ar",
        )
        baker.make(
            AssetVersion,
            asset=asset,
            name="v1",
            file_url=SimpleUploadedFile("v1.csv", b"1,1,text", content_type="text/csv"),
        )
        return asset

    def test_list_versions_where_file_stored_locally_should_return_absolute_file_url(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)
        asset = self._asset_with_file(CategoryChoice.TAFSIR, "local-file-tafsir")

        # Act
        response = self.client.get(f"/portal/tafsirs/{asset.slug}/versions/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        file_url = response.json()["results"][0]["file_url"]
        self.assertTrue(file_url.startswith("http://testserver/media/"), file_url)

    def test_list_mushaf_versions_where_file_stored_locally_should_return_absolute_file_url(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_MUSHAF)
        asset = self._asset_with_file(CategoryChoice.MUSHAF, "local-file-mushaf")

        # Act
        response = self.client.get(f"/portal/mushafs/{asset.slug}/versions/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        file_url = response.json()["results"][0]["file_url"]
        self.assertTrue(file_url.startswith("http://testserver/media/"), file_url)
