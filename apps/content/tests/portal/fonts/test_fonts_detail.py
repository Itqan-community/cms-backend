from model_bakery import baker

from apps.content.models import Asset, AssetVersion, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class FontDetailTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.font = baker.make(
            Asset,
            category=CategoryChoice.FONT,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Font Al-Madinah",
            name_ar="خط عثماني",
            name_en="Font Al-Madinah",
            description="A comprehensive font",
            description_ar="خط شامل",
            description_en="A comprehensive font",
            long_description_ar="شرح طويل بالعربية",
            long_description_en="Long explanation in English",
            license="CC-BY",
        )

        # Create asset versions
        self.version1 = baker.make(AssetVersion, asset=self.font, name="Version 1.0", size_bytes=1024)
        self.version2 = baker.make(AssetVersion, asset=self.font, name="Version 2.0", size_bytes=2048)

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)

    def test_retrieve_font_where_valid_slug_should_return_all_fields(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_FONT)
        response = self.client.get(f"/portal/fonts/{self.font.slug}/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Check localized fields
        self.assertEqual(self.font.slug, body["slug"])
        self.assertEqual("خط عثماني", body["name_ar"])
        self.assertEqual("Font Al-Madinah", body["name_en"])
        self.assertEqual("خط شامل", body["description_ar"])
        self.assertEqual("A comprehensive font", body["description_en"])
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

    def test_retrieve_font_where_not_found_should_return_404(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_FONT)
        response = self.client.get("/portal/fonts/nonexistent-slug/")

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("font_not_found", body["error_name"])

    def test_retrieve_font_where_unauthenticated_should_return_401(self):
        response = self.client.get(f"/portal/fonts/{self.font.slug}/")
        self.assertEqual(401, response.status_code)

    def test_retrieve_font_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.get(f"/portal/fonts/{self.font.slug}/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
