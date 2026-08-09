from model_bakery import baker

from apps.content.models import Asset, AssetVersion, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class MushafDetailTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.mushaf = baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Mushaf Al-Madinah",
            name_ar="مصحف المدينة",
            name_en="Mushaf Al-Madinah",
            description="A comprehensive mushaf",
            description_ar="مصحف شامل",
            description_en="A comprehensive mushaf",
            long_description_ar="شرح طويل بالعربية",
            long_description_en="Long explanation in English",
            license="CC-BY",
        )

        # Create asset versions
        self.version1 = baker.make(AssetVersion, asset=self.mushaf, name="Version 1.0", size_bytes=1024)
        self.version2 = baker.make(AssetVersion, asset=self.mushaf, name="Version 2.0", size_bytes=2048)

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)

    def test_retrieve_mushaf_where_valid_slug_should_return_all_fields(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_MUSHAF)
        response = self.client.get(f"/portal/mushafs/{self.mushaf.slug}/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Check localized fields
        self.assertEqual(self.mushaf.slug, body["slug"])
        self.assertEqual("مصحف المدينة", body["name_ar"])
        self.assertEqual("Mushaf Al-Madinah", body["name_en"])
        self.assertEqual("مصحف شامل", body["description_ar"])
        self.assertEqual("A comprehensive mushaf", body["description_en"])
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

    def test_retrieve_mushaf_where_not_found_should_return_404(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_MUSHAF)
        response = self.client.get("/portal/mushafs/nonexistent-slug/")

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("mushaf_not_found", body["error_name"])

    def test_retrieve_mushaf_where_unauthenticated_should_return_401(self):
        response = self.client.get(f"/portal/mushafs/{self.mushaf.slug}/")
        self.assertEqual(401, response.status_code)

    def test_retrieve_mushaf_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.get(f"/portal/mushafs/{self.mushaf.slug}/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
