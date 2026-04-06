from model_bakery import baker

from apps.content.models import Asset, Resource, ResourceVersion
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TranslationDetailTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.TRANSLATION,
            status=Resource.StatusChoice.READY,
        )
        self.translation = baker.make(
            Asset,
            category=Resource.CategoryChoice.TRANSLATION,
            resource=self.resource,
            name="Sahih International",
            name_ar="ترجمة صحيح إنترناشيونال",
            name_en="Sahih International",
            description="English translation of the Quran",
            description_ar="ترجمة القرآن الكريم باللغة الإنجليزية",
            description_en="English translation of the Quran",
            long_description_ar="ترجمة تفصيلية",
            long_description_en="Detailed English translation",
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

    def test_detail_returns_all_localized_fields_and_versions(self):
        self.authenticate_user(self.user)
        response = self.client.get(f"/portal/translations/{self.translation.slug}/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Check localized fields
        self.assertEqual("ترجمة صحيح إنترناشيونال", body["name_ar"])
        self.assertEqual("Sahih International", body["name_en"])
        self.assertEqual("ترجمة القرآن الكريم باللغة الإنجليزية", body["description_ar"])
        self.assertEqual("English translation of the Quran", body["description_en"])
        self.assertEqual("ترجمة تفصيلية", body["long_description_ar"])
        self.assertEqual("Detailed English translation", body["long_description_en"])

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

    def test_detail_not_found_returns_404(self):
        self.authenticate_user(self.user)
        response = self.client.get("/portal/translations/nonexistent-slug/")

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("translation_not_found", body["error_name"])

    def test_detail_unauthenticated_returns_401(self):
        response = self.client.get(f"/portal/translations/{self.translation.slug}/")
        self.assertEqual(401, response.status_code)
