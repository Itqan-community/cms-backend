from model_bakery import baker

from apps.content.models import Asset, AssetLanguage, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class AssetLanguagesApiTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.translation = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="French Rashid",
            slug="french-rashid",
            language="ar",
        )
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)

    def test_list_languages_returns_source_first(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        AssetLanguage.objects.create(asset=self.translation, language="es")

        response = self.client.get(f"/portal/content/translations/{self.translation.slug}/languages/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertTrue(body[0]["is_source"])
        self.assertEqual("ar", body[0]["language"])

    def test_add_language_creates_non_source(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)

        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/languages/",
            data={"language": "es"},
            content_type="application/json",
        )

        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(response.json()["is_source"])
        self.assertTrue(AssetLanguage.objects.filter(asset=self.translation, language="es").exists())

    def test_add_duplicate_language_returns_400(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        AssetLanguage.objects.create(asset=self.translation, language="es")

        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/languages/",
            data={"language": "es"},
            content_type="application/json",
        )

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("language_exists", response.json()["error_name"])

    def test_add_language_without_permission_returns_403(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)

        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/languages/",
            data={"language": "es"},
            content_type="application/json",
        )

        self.assertEqual(403, response.status_code, response.content)
