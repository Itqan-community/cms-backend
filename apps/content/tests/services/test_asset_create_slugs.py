from unittest.mock import patch

from django.test import override_settings
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, Qiraah, Reciter, Riwayah
from apps.content.repositories.asset_slug import AssetSlugRepository
from apps.core.gemini import GeminiClient
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


def _text_asset(publisher: Publisher, **overrides) -> dict:
    data = {
        "name_ar": "اسم الأصل",
        "name_en": "",
        "description_ar": "وصف",
        "description_en": "Description",
        "license": "CC-BY",
        "language": "ar",
        "publisher_id": publisher.id,
        "is_external": False,
    }
    data.update(overrides)
    return data


# A configured key proves creation stays AI-free even when Gemini is available.
@override_settings(GEMINI_API_KEY="test-key")
class AssetCreateSlugTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.reciter = baker.make(Reciter, name_en="Saad Al Ghamdi", name_ar="سعد الغامدي")
        self.qiraah = baker.make(Qiraah, name_en="Asim", name_ar="عاصم")
        self.riwayah = baker.make(Riwayah, qiraah=self.qiraah, name_en="Hafs", name_ar="حفص")

    def _grant_all(self) -> None:
        for permission in (
            PermissionChoice.PORTAL_CREATE_MUSHAF,
            PermissionChoice.PORTAL_CREATE_TAFSIR,
            PermissionChoice.PORTAL_CREATE_TRANSLATION,
            PermissionChoice.PORTAL_CREATE_FONT,
            PermissionChoice.PORTAL_CREATE_RECITATION,
        ):
            self.give_permission(self.user, permission)

    def _recitation(self, **overrides) -> dict:
        data = {
            "name_ar": "تلاوة",
            "publisher_id": self.publisher.id,
            "reciter_id": self.reciter.id,
            "qiraah_id": self.qiraah.id,
            "riwayah_id": self.riwayah.id,
            "license": "CC0",
        }
        data.update(overrides)
        return data

    def _post(self, url: str, data: dict):
        if url == "/portal/recitations/":
            return self.client.post(url, data=data, content_type="application/json")
        return self.client.post(url, data=data)

    def test_create_asset_where_no_slug_sent_should_build_template_slug_without_calling_ai(self):
        # Arrange
        self.authenticate_user(self.user)
        self._grant_all()
        cases = [
            ("/portal/mushafs/", _text_asset(self.publisher, name_en="Warsh Mushaf"), "mushaf-warsh"),
            (
                "/portal/tafsirs/",
                _text_asset(self.publisher, name_en="Tafsir Al Saadi", template="ayah"),
                "tafsir-al-saadi",
            ),
            (
                "/portal/translations/",
                _text_asset(self.publisher, name_en="Hamidullah", language="fr", template="ayah"),
                "translation-fr-hamidullah",
            ),
            ("/portal/fonts/", _text_asset(self.publisher, name_en="Warsh Font"), "font-warsh"),
            ("/portal/recitations/", self._recitation(), "recitation-saad-al-ghamdi-hafs"),
        ]

        # Act
        with patch.object(GeminiClient, GeminiClient.generate_json.__name__) as ai:
            responses = [(self._post(url, data), expected) for url, data, expected in cases]

        # Assert
        for response, expected in responses:
            self.assertEqual(201, response.status_code, response.content)
            self.assertEqual(expected, Asset.objects.get(id=response.json()["id"]).slug)
        ai.assert_not_called()

    def test_create_asset_where_suggested_slug_sent_should_store_it_without_calling_ai(self):
        # Arrange
        self.authenticate_user(self.user)
        self._grant_all()
        cases = [
            ("/portal/mushafs/", _text_asset(self.publisher, slug="mushaf-madinah-hafs")),
            ("/portal/tafsirs/", _text_asset(self.publisher, template="ayah", slug="tafsir-ibn-kathir")),
            (
                "/portal/translations/",
                _text_asset(self.publisher, language="en", template="ayah", slug="translation-en-sahih-international"),
            ),
            ("/portal/fonts/", _text_asset(self.publisher, slug="font-uthmanic-hafs")),
            ("/portal/recitations/", self._recitation(slug="recitation-saad-al-ghamdi-hafs")),
        ]

        # Act
        with patch.object(GeminiClient, GeminiClient.generate_json.__name__) as ai:
            responses = [(self._post(url, data), data["slug"]) for url, data in cases]

        # Assert
        for response, expected in responses:
            self.assertEqual(201, response.status_code, response.content)
            self.assertEqual(expected, Asset.objects.get(id=response.json()["id"]).slug)
        ai.assert_not_called()

    def test_create_tafsir_where_slug_invalid_should_return_400_asset_slug_invalid(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.post(
            "/portal/tafsirs/", data=_text_asset(self.publisher, template="ayah", slug="mushaf-not-a-tafsir")
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("asset_slug_invalid", response.json()["error_name"])
        self.assertFalse(Asset.objects.filter(slug="mushaf-not-a-tafsir").exists())

    def test_create_recitation_where_slug_invalid_should_return_400_asset_slug_invalid(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_RECITATION)

        # Act
        response = self._post("/portal/recitations/", self._recitation(slug="Recitation Saad"))

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("asset_slug_invalid", response.json()["error_name"])

    def test_create_font_where_suggested_slug_taken_since_should_append_suffix(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_FONT)
        baker.make(Asset, slug="font-uthmanic-hafs", category=CategoryChoice.FONT, publisher=self.publisher)

        # Act
        response = self.client.post("/portal/fonts/", data=_text_asset(self.publisher, slug="font-uthmanic-hafs"))

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("font-uthmanic-hafs-2", Asset.objects.get(id=response.json()["id"]).slug)

    def test_create_font_where_slug_taken_between_check_and_insert_should_retry_with_suffix(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_FONT)
        baker.make(Asset, slug="font-uthmanic-hafs", category=CategoryChoice.FONT, publisher=self.publisher)

        # Act: the existence check misses the row, as when a concurrent create commits in between
        with patch.object(AssetSlugRepository, AssetSlugRepository.slug_exists.__name__, return_value=False):
            response = self.client.post("/portal/fonts/", data=_text_asset(self.publisher, slug="font-uthmanic-hafs"))

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("font-uthmanic-hafs-2", Asset.objects.get(id=response.json()["id"]).slug)
