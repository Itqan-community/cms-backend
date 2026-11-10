from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, AssetVersion, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TextAssetDetailTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.text_asset = baker.make(
            Asset,
            category=CategoryChoice.TEXT,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Text asset Al-Tabari",
            name_ar="تفسير الطبري",
            name_en="Text asset Al-Tabari",
            description="A comprehensive text_asset",
            description_ar="تفسير شامل",
            description_en="A comprehensive text_asset",
            long_description_ar="شرح طويل بالعربية",
            long_description_en="Long explanation in English",
            license="CC-BY",
        )

        # Create asset versions
        self.version1 = baker.make(AssetVersion, asset=self.text_asset, name="Version 1.0", size_bytes=1024)
        self.version2 = baker.make(AssetVersion, asset=self.text_asset, name="Version 2.0", size_bytes=2048)

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)

    def test_retrieve_text_asset_where_valid_slug_should_return_all_fields(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        response = self.client.get(f"/portal/text-assets/{self.text_asset.slug}/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Check localized fields
        self.assertEqual(self.text_asset.slug, body["slug"])
        self.assertEqual("تفسير الطبري", body["name_ar"])
        self.assertEqual("Text asset Al-Tabari", body["name_en"])
        self.assertEqual("تفسير شامل", body["description_ar"])
        self.assertEqual("A comprehensive text_asset", body["description_en"])
        self.assertEqual("شرح طويل بالعربية", body["long_description_ar"])
        self.assertEqual("Long explanation in English", body["long_description_en"])

        # Check publisher
        self.assertEqual(self.publisher.id, body["publisher"]["id"])
        self.assertEqual(self.publisher.name, body["publisher"]["name"])

        # Check license
        self.assertEqual("CC-BY", body["license"])

        # Check versions
        self.assertEqual(2, len(body["versions"]))
        version_names = {v["name"] for v in body["versions"]}
        self.assertIn("Version 1.0", version_names)
        self.assertIn("Version 2.0", version_names)

        # Check version fields
        for version in body["versions"]:
            self.assertIn("id", version)
            self.assertIn("name", version)
            self.assertIn("size_bytes", version)
            self.assertIn("created_at", version)

    def test_retrieve_text_asset_where_not_found_should_return_404(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TEXT_ASSET)
        response = self.client.get("/portal/text-assets/nonexistent-slug/")

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("text_asset_not_found", body["error_name"])

    def test_retrieve_text_asset_where_unauthenticated_should_return_401(self):
        response = self.client.get(f"/portal/text-assets/{self.text_asset.slug}/")
        self.assertEqual(401, response.status_code)

    def test_retrieve_text_asset_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.get(f"/portal/text-assets/{self.text_asset.slug}/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
