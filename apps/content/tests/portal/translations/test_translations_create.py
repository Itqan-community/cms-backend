from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TranslationCreateTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_create_translation_where_valid_data_should_return_201(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_TRANSLATION)
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

        self.assertIsNotNone(body["id"])
        self.assertEqual("ترجمة صحيح إنترناشيونال", body["name_ar"])
        self.assertEqual("Sahih International", body["name_en"])
        self.assertEqual("CC-BY", body["license"])
        self.assertEqual("en", body["language"])
        self.assertIn("slug", body)
        self.assertEqual(self.publisher.id, body["publisher"]["id"])

        # Verify in database
        asset = Asset.objects.get(id=body["id"])
        self.assertEqual(CategoryChoice.TRANSLATION, asset.category)
        self.assertEqual(StatusChoice.READY, asset.status)
        self.assertEqual("en", asset.language)

    def test_create_translation_where_publisher_not_found_should_return_404(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_TRANSLATION)
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

    def test_create_translation_where_name_missing_should_return_400(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_TRANSLATION)
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

    def test_create_translation_where_unauthenticated_should_return_401(self):
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

    def test_create_translation_where_only_english_name_should_create_successfully(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_TRANSLATION)
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

    def test_create_translation_where_is_external_true_and_url_present_should_return_201(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_TRANSLATION)
        response = self.client.post(
            "/portal/translations/",
            data={
                "name_ar": "ترجمة خارجية",
                "name_en": "External Translation",
                "license": "CC-BY",
                "language": "en",
                "publisher_id": self.publisher.id,
                "is_external": True,
                "external_url": "https://example.com/translation",
            },
            content_type="application/json",
        )

        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertTrue(body["is_external"])
        self.assertEqual("https://example.com/translation", body["external_url"])

    def test_create_translation_where_is_external_true_and_no_url_should_return_400(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_TRANSLATION)
        response = self.client.post(
            "/portal/translations/",
            data={
                "name_ar": "ترجمة خارجية",
                "name_en": "External Translation",
                "license": "CC-BY",
                "language": "en",
                "publisher_id": self.publisher.id,
                "is_external": True,
                "external_url": "",  # explicitly empty/absent
            },
            content_type="application/json",
        )

        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("external_url_required", body["error_name"])

    def test_create_translation_where_user_lacks_permission_should_return_403(self):
        user_without_permission = User.objects.create_user(email="noperm@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)
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
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
