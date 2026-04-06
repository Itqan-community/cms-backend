from model_bakery import baker

from apps.content.models import Asset, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TranslationCreateTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_create_translation_valid_data_returns_201(self):
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/translations/",
            data={
                "name_ar": "ترجمة صحيح إنترناشيونال",
                "name_en": "Sahih International",
                "description_ar": "ترجمة القرآن الكريم",
                "description_en": "Translation of the Quran",
                "long_description_ar": "ترجمة تفصيلية",
                "long_description_en": "Detailed translation",
                "license": "CC-BY",
                "language": "en",
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
        self.assertEqual("ترجمة صحيح إنترناشيونال", body["name_ar"])
        self.assertEqual("Sahih International", body["name_en"])
        self.assertEqual("CC-BY", body["license"])
        self.assertEqual(self.publisher.id, body["publisher"]["id"])

        # Verify in database
        asset = Asset.objects.get(id=body["id"])
        self.assertEqual(Resource.CategoryChoice.TRANSLATION, asset.category)
        self.assertEqual(Resource.StatusChoice.READY, asset.resource.status)

    def test_create_translation_invalid_publisher_returns_404(self):
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/translations/",
            data={
                "name_ar": "ترجمة",
                "name_en": "Translation",
                "description_ar": "وصف",
                "description_en": "Description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY",
                "language": "en",
                "publisher_id": 99999,  # Non-existent publisher
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_not_found", body["error_name"])

    def test_create_translation_missing_name_returns_400(self):
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/translations/",
            data={
                "name_ar": "",  # Empty name
                "name_en": "",  # Empty name
                "description_ar": "وصف",
                "description_en": "Description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY",
                "language": "en",
                "publisher_id": self.publisher.id,
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("translation_name_required", body["error_name"])

    def test_create_translation_unauthenticated_returns_401(self):
        response = self.client.post(
            "/portal/translations/",
            data={
                "name_ar": "ترجمة",
                "name_en": "Translation",
                "description_ar": "وصف",
                "description_en": "Description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY",
                "language": "en",
                "publisher_id": self.publisher.id,
                "is_external": False,
                "external_url": None,
            },
            content_type="application/json",
        )

        self.assertEqual(401, response.status_code, response.content)

    def test_create_translation_with_only_english_name(self):
        self.authenticate_user(self.user)
        response = self.client.post(
            "/portal/translations/",
            data={
                "name_ar": "",
                "name_en": "English Translation",
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
        self.assertEqual("English Translation", body["name_en"])
