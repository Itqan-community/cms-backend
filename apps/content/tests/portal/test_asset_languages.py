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
        # These suites exercise editing, not language assignment: give the user the
        # assignment bypass so they behave like the existing editor groups that the
        # rollout migration grants it to. Assignment itself is covered by its own tests.
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
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
        # The source rendition is available to consumers; the added translation is not.
        self.assertTrue(body[0]["is_available"])
        es_row = next(row for row in body if row["language"] == "es")
        self.assertFalse(es_row["is_available"])

    def test_add_language_creates_non_source_pending(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_ADD_ASSET_LANGUAGE)

        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/languages/",
            data={"language": "es"},
        )

        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(response.json()["is_source"])
        # A newly added translation starts hidden from consumers (pending).
        self.assertFalse(response.json()["is_available"])
        es = AssetLanguage.objects.get(asset=self.translation, language="es")
        self.assertEqual(StatusChoice.DRAFT, es.status)

    def test_mark_language_available_requires_published_version(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        AssetLanguage.objects.create(asset=self.translation, language="es")

        response = self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/languages/es/availability/",
            data={"available": True},
            content_type="application/json",
        )

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("language_has_no_published_version", response.json()["error_name"])

    def test_mark_language_available_then_pending(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        es = AssetLanguage.objects.create(asset=self.translation, language="es")
        baker.make(AssetVersion, asset=self.translation, asset_language=es, state=VersionStateChoice.PUBLISHED)

        # Mark available
        response = self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/languages/es/availability/",
            data={"available": True},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(response.json()["is_available"])
        es.refresh_from_db()
        self.assertEqual(StatusChoice.READY, es.status)

        # Mark pending again
        response = self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/languages/es/availability/",
            data={"available": False},
            content_type="application/json",
        )
        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(response.json()["is_available"])
        es.refresh_from_db()
        self.assertEqual(StatusChoice.DRAFT, es.status)

    def test_mark_language_available_without_permission_returns_403(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        AssetLanguage.objects.create(asset=self.translation, language="es")

        response = self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/languages/es/availability/",
            data={"available": True},
            content_type="application/json",
        )

        self.assertEqual(403, response.status_code, response.content)

    def test_add_duplicate_language_returns_400(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_ADD_ASSET_LANGUAGE)
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
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_ADD_ASSET_LANGUAGE)
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

    def test_add_language_with_unparseable_file_returns_400_and_rolls_back(self):
        # A malformed upload must be rejected (the endpoint declares
        # content_file_unparseable) and must not leave the language registered
        # without its requested version.
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_ADD_ASSET_LANGUAGE)
        bad = SimpleUploadedFile("es.csv", b"not,a,valid\nheaderless garbage", content_type="text/csv")

        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/languages/",
            data={"language": "es", "file": bad},
        )

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("content_file_unparseable", response.json()["error_name"])
        # Registration rolled back with the failed upload.
        self.assertFalse(AssetLanguage.objects.filter(asset=self.translation, language="es").exists())
        self.assertFalse(AssetVersion.objects.filter(asset=self.translation, asset_language__language="es").exists())
