from model_bakery import baker

from apps.content.models import Asset, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TafsirCreateTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_create_tafsir_valid_data_returns_201(self):
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "تفسير الطبري",
                "name_en": "Tafsir Al-Tabari",
                "description_ar": "تفسير شامل",
                "description_en": "A comprehensive tafsir",
                "long_description_ar": "شرح تفصيلي",
                "long_description_en": "Detailed explanation",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(201, response.status_code, response.content)
        body = response.json()

        # Check that asset and resource were created
        self.assertIsNotNone(body["id"])
        self.assertEqual("تفسير الطبري", body["name_ar"])
        self.assertEqual("Tafsir Al-Tabari", body["name_en"])
        self.assertEqual("CC-BY", body["license"])
        self.assertEqual(self.publisher.id, body["publisher"]["id"])

        # Verify in database
        asset = Asset.objects.get(id=body["id"])
        self.assertEqual(Resource.CategoryChoice.TAFSIR, asset.category)
        self.assertEqual(Resource.StatusChoice.READY, asset.resource.status)

    def test_create_tafsir_invalid_publisher_returns_404(self):
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "تفسير",
                "name_en": "Tafsir",
                "description_ar": "وصف",
                "description_en": "Description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": 99999,  # Non-existent publisher
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_not_found", body["error_name"])

    def test_create_tafsir_missing_name_returns_400(self):
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "",  # Empty name
                "name_en": "",  # Empty name
                "description_ar": "وصف",
                "description_en": "Description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("tafsir_name_required", body["error_name"])

    def test_create_tafsir_unauthenticated_returns_401(self):
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "تفسير",
                "name_en": "Tafsir",
                "description_ar": "وصف",
                "description_en": "Description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(401, response.status_code, response.content)

    def test_create_tafsir_with_only_english_name(self):
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "",
                "name_en": "English Tafsir",
                "description_ar": "",
                "description_en": "English description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY-SA",
                "language": "en",
                "publisher_id": self.publisher.id,
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("English Tafsir", body["name_en"])
