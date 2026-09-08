from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, AssetLanguage, AssetVersion, CategoryChoice, StatusChoice, VersionStateChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura
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
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayahs = [baker.make(Ayah, id=i, sura=self.sura, number_in_sura=i, text=f"ayah {i}") for i in (1, 2, 3)]

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
        )

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("language_exists", response.json()["error_name"])

    def test_add_language_without_permission_returns_403(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)

        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/languages/",
            data={"language": "es"},
        )

        self.assertEqual(403, response.status_code, response.content)

    def test_add_language_with_file_creates_first_version_and_entries(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        csv = SimpleUploadedFile("es.csv", b"surah,ayah,text\n1,1,en el nombre\n1,2,alabado", content_type="text/csv")

        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/languages/",
            data={"language": "es", "file": csv},
        )

        self.assertEqual(200, response.status_code, response.content)
        # The language now has a published version seeded from the uploaded file.
        version = AssetVersion.objects.get(
            asset=self.translation, asset_language__language="es", state=VersionStateChoice.PUBLISHED
        )
        self.assertEqual(2, version.entries.count())
        self.assertEqual("en el nombre", version.entries.get(ayah_id=self.ayahs[0].id).text)
