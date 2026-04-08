from model_bakery import baker

from apps.content.models import Asset, Resource, ResourceVersion
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TafsirDetailTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        self.tafsir = baker.make(
            Asset,
            category=Resource.CategoryChoice.TAFSIR,
            resource=self.resource,
            name="Tafsir Al-Tabari",
            name_ar="تفسير الطبري",
            name_en="Tafsir Al-Tabari",
            description="A comprehensive tafsir",
            description_ar="تفسير شامل",
            description_en="A comprehensive tafsir",
            long_description_ar="شرح طويل بالعربية",
            long_description_en="Long explanation in English",
            license="CC-BY",
        )

        # Create resource versions
        self.version1 = baker.make(
            ResourceVersion,
            resource=self.resource,
            name="Version 1.0",
            semvar="1.0.0",
            size_bytes=1024,
        )
        self.version2 = baker.make(
            ResourceVersion,
            resource=self.resource,
            name="Version 2.0",
            semvar="2.0.0",
            size_bytes=2048,
        )

        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_retrieve_tafsir_where_valid_slug_should_return_all_fields(self):
        self.authenticate_user(self.user)
        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Check localized fields
        self.assertEqual(self.tafsir.slug, body["slug"])
        self.assertEqual("تفسير الطبري", body["name_ar"])
        self.assertEqual("Tafsir Al-Tabari", body["name_en"])
        self.assertEqual("تفسير شامل", body["description_ar"])
        self.assertEqual("A comprehensive tafsir", body["description_en"])
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

    def test_retrieve_tafsir_where_not_found_should_return_404(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/tafsirs/nonexistent-slug/")

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("tafsir_not_found", body["error_name"])

    def test_retrieve_tafsir_where_unauthenticated_should_return_401(self):
        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/")
        self.assertEqual(401, response.status_code)
