from unittest.mock import patch

from model_bakery import baker

from apps.content.models import Reciter, Riwayah
from apps.core.gemini import GeminiClient, GeminiQuotaExceeded, GeminiRateLimited, GeminiUnavailable
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.core.wikipedia import WikiArticle, WikipediaClient
from apps.users.models import User

URL = "/portal/ai/translate/"


class AiTranslateApiTests(BaseTestCase):
    def _admin(self, permission: PermissionChoice = PermissionChoice.PORTAL_CREATE_TAFSIR) -> User:
        user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.give_permission(user, permission)
        return user

    def test_ai_translate_where_mode_translate_should_return_english_fields(self):
        # Arrange
        self.authenticate_user(self._admin())
        payload = {
            "mode": "translate",
            "category": "tafsir",
            "fields": {"name": "تفسير ابن كثير", "description": "تفسير"},
        }

        # Act
        with (
            patch.object(
                GeminiClient,
                GeminiClient.generate_json.__name__,
                return_value={"name": "Tafsir Ibn Kathir", "description": "A tafsir."},
            ) as ai,
            patch.object(WikipediaClient, WikipediaClient.lookup.__name__) as wiki,
        ):
            response = self.client.post(URL, data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            {"fields": {"name": "Tafsir Ibn Kathir", "description": "A tafsir."}, "sources": [], "slug": None},
            response.json(),
        )
        self.assertEqual({"name", "description"}, set(ai.call_args.kwargs["schema"]["properties"]))
        # Without "required" the model may silently drop fields (seen live: description omitted).
        self.assertEqual(["description", "name"], ai.call_args.kwargs["schema"]["required"])
        wiki.assert_not_called()

    def test_ai_translate_where_mode_web_should_use_wikipedia_notes_and_return_their_urls(self):
        # Arrange
        self.authenticate_user(self._admin(PermissionChoice.PORTAL_CREATE_RECITER))
        payload = {"mode": "web", "category": "reciter", "fields": {"name": "مشاري العفاسي", "bio": ""}}
        articles = [WikiArticle(url="https://en.wikipedia.org/wiki/A", extract="Kuwaiti reciter born 1976.")]

        # Act
        with (
            patch.object(WikipediaClient, WikipediaClient.lookup.__name__, return_value=articles) as wiki,
            patch.object(
                GeminiClient,
                GeminiClient.generate_json.__name__,
                return_value={"name": "Mishary Rashid Alafasy", "bio": "A Kuwaiti reciter born in 1976."},
            ) as structured,
        ):
            response = self.client.post(URL, data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(["https://en.wikipedia.org/wiki/A"], body["sources"])
        self.assertEqual("Mishary Rashid Alafasy", body["fields"]["name"])
        self.assertEqual("A Kuwaiti reciter born in 1976.", body["fields"]["bio"])
        wiki.assert_called_once_with("مشاري العفاسي")
        self.assertIn("Kuwaiti reciter born 1976.", structured.call_args.kwargs["prompt"])
        self.assertEqual({"name", "bio"}, set(structured.call_args.kwargs["schema"]["properties"]))

    def test_ai_translate_where_web_mode_for_recitation_should_search_the_reciter(self):
        # Arrange
        self.authenticate_user(self._admin(PermissionChoice.PORTAL_CREATE_RECITATION))
        payload = {
            "mode": "web",
            "category": "recitation",
            "fields": {"name": "تلاوة برواية حفص", "description": ""},
            "context": {"reciter": "سعد الغامدي", "riwayah": "حفص"},
        }

        # Act
        with (
            patch.object(WikipediaClient, WikipediaClient.lookup.__name__, return_value=[]) as wiki,
            patch.object(
                GeminiClient, GeminiClient.generate_json.__name__, return_value={"name": "x", "description": "y"}
            ),
        ):
            response = self.client.post(URL, data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        wiki.assert_called_once_with("سعد الغامدي")

    def test_ai_translate_where_wikipedia_finds_nothing_should_translate_without_notes(self):
        # Arrange
        self.authenticate_user(self._admin())
        payload = {"mode": "web", "category": "tafsir", "fields": {"name": "تفسير", "description": "وصف"}}

        # Act
        with (
            patch.object(WikipediaClient, WikipediaClient.lookup.__name__, return_value=[]),
            patch.object(
                GeminiClient, GeminiClient.generate_json.__name__, return_value={"name": "Tafsir", "description": "x"}
            ) as structured,
        ):
            response = self.client.post(URL, data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json()["sources"])
        self.assertNotIn("Wikipedia", structured.call_args.kwargs["prompt"])

    def test_ai_translate_where_context_given_should_include_it_in_prompt(self):
        # Arrange
        self.authenticate_user(self._admin(PermissionChoice.PORTAL_CREATE_RECITATION))
        payload = {
            "mode": "translate",
            "category": "recitation",
            "fields": {"name": "تلاوة"},
            "context": {"reciter": "سعد الغامدي", "riwayah": "حفص"},
        }

        # Act
        with patch.object(GeminiClient, GeminiClient.generate_json.__name__, return_value={"name": "Recitation"}) as ai:
            response = self.client.post(URL, data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn("سعد الغامدي", ai.call_args.kwargs["prompt"])
        self.assertIn("حفص", ai.call_args.kwargs["prompt"])

    def test_ai_translate_where_all_fields_blank_should_return_400_ai_translate_empty(self):
        # Arrange
        self.authenticate_user(self._admin())

        # Act
        with patch.object(GeminiClient, GeminiClient.generate_json.__name__) as ai:
            response = self.client.post(
                URL,
                data={"mode": "translate", "category": "tafsir", "fields": {"name": "  "}},
                content_type="application/json",
            )

        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("ai_translate_empty", response.json()["error_name"])
        ai.assert_not_called()

    def test_ai_translate_where_gemini_429_should_return_429_ai_quota_exceeded(self):
        # Arrange
        self.authenticate_user(self._admin())

        # Act
        with patch.object(GeminiClient, GeminiClient.generate_json.__name__, side_effect=GeminiQuotaExceeded("x")):
            response = self.client.post(
                URL,
                data={"mode": "translate", "category": "tafsir", "fields": {"name": "تفسير"}},
                content_type="application/json",
            )

        # Assert
        self.assertEqual(429, response.status_code)
        self.assertEqual("ai_quota_exceeded", response.json()["error_name"])

    def test_ai_translate_where_gemini_per_minute_limit_should_return_429_ai_rate_limited(self):
        # Arrange
        self.authenticate_user(self._admin())

        # Act
        with patch.object(GeminiClient, GeminiClient.generate_json.__name__, side_effect=GeminiRateLimited("x")):
            response = self.client.post(
                URL,
                data={"mode": "translate", "category": "tafsir", "fields": {"name": "تفسير"}},
                content_type="application/json",
            )

        # Assert
        self.assertEqual(429, response.status_code)
        self.assertEqual("ai_rate_limited", response.json()["error_name"])

    def test_ai_translate_where_gemini_unavailable_should_return_503_ai_unavailable(self):
        # Arrange
        self.authenticate_user(self._admin())

        # Act
        with patch.object(GeminiClient, GeminiClient.generate_json.__name__, side_effect=GeminiUnavailable("x")):
            response = self.client.post(
                URL,
                data={"mode": "translate", "category": "tafsir", "fields": {"name": "تفسير"}},
                content_type="application/json",
            )

        # Assert
        self.assertEqual(503, response.status_code)
        self.assertEqual("ai_unavailable", response.json()["error_name"])

    def test_ai_translate_where_ai_omits_a_field_should_return_only_requested_non_empty_keys(self):
        # Arrange
        self.authenticate_user(self._admin())

        # Act
        with patch.object(
            GeminiClient,
            GeminiClient.generate_json.__name__,
            return_value={"name": "Tafsir Al-Saadi", "description": "  ", "extra": "x"},
        ):
            response = self.client.post(
                URL,
                data={
                    "mode": "translate",
                    "category": "tafsir",
                    "fields": {"name": "تفسير السعدي", "description": "وصف"},
                },
                content_type="application/json",
            )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"name": "Tafsir Al-Saadi"}, response.json()["fields"])

    def test_ai_translate_where_unknown_field_key_should_return_400_validation_error(self):
        # Arrange
        self.authenticate_user(self._admin())

        # Act
        response = self.client.post(
            URL,
            data={"mode": "translate", "category": "tafsir", "fields": {"password": "x"}},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_ai_translate_where_user_lacks_create_permissions_should_return_403(self):
        # Arrange
        user = User.objects.create_user(email="viewer@example.com", name="Viewer", is_staff=True)
        self.authenticate_user(user)

        # Act
        response = self.client.post(
            URL,
            data={"mode": "translate", "category": "tafsir", "fields": {"name": "تفسير"}},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_ai_translate_where_slug_for_given_should_return_slug_from_the_same_call(self):
        # Arrange
        self.authenticate_user(self._admin())
        payload = {
            "mode": "translate",
            "category": "tafsir",
            "fields": {"name": "تفسير ابن كثير"},
            "slug_for": {"name_ar": "تفسير ابن كثير", "name_en": ""},
        }

        # Act
        with patch.object(
            GeminiClient,
            GeminiClient.generate_json.__name__,
            return_value={"name": "Tafsir Ibn Kathir", "slug_words": ["ibn", "kathir"]},
        ) as ai:
            response = self.client.post(URL, data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("tafsir-ibn-kathir", response.json()["slug"])
        self.assertEqual({"name": "Tafsir Ibn Kathir"}, response.json()["fields"])
        ai.assert_called_once()
        self.assertIn("slug_words", ai.call_args.kwargs["schema"]["required"])

    def test_ai_translate_where_only_slug_needed_should_make_one_call_for_it(self):
        # Arrange
        self.authenticate_user(self._admin(PermissionChoice.PORTAL_CREATE_TRANSLATION))
        payload = {
            "mode": "translate",
            "category": "translation",
            "fields": {},
            "slug_for": {"name_ar": "صحيح انترناشونال", "name_en": "Sahih International", "language": "en"},
        }

        # Act
        with patch.object(
            GeminiClient,
            GeminiClient.generate_json.__name__,
            return_value={"slug_words": ["sahih", "international"]},
        ) as ai:
            response = self.client.post(URL, data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"fields": {}, "sources": [], "slug": "translation-en-sahih-international"}, response.json())
        self.assertEqual(["slug_words"], ai.call_args.kwargs["schema"]["required"])

    def test_ai_translate_where_recitation_slug_should_use_reciter_and_riwayah(self):
        # Arrange
        self.authenticate_user(self._admin(PermissionChoice.PORTAL_CREATE_RECITATION))
        reciter = baker.make(Reciter, name_en="", name_ar="سعد الغامدي")
        riwayah = baker.make(Riwayah, name_en="Hafs", name_ar="حفص")
        payload = {
            "mode": "translate",
            "category": "recitation",
            "fields": {"name": "تلاوة"},
            "slug_for": {"name_ar": "تلاوة", "reciter_id": reciter.id, "riwayah_id": riwayah.id, "year": 1440},
        }

        # Act
        with patch.object(
            GeminiClient,
            GeminiClient.generate_json.__name__,
            return_value={"name": "Recitation", "slug_words": ["saad", "al", "ghamdi", "hafs"]},
        ) as ai:
            response = self.client.post(URL, data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("recitation-saad-al-ghamdi-hafs", response.json()["slug"])
        self.assertIn("سعد الغامدي", ai.call_args.kwargs["prompt"])

    def test_ai_translate_where_ai_returns_no_slug_words_should_return_null_slug(self):
        # Arrange
        self.authenticate_user(self._admin())
        payload = {
            "mode": "translate",
            "category": "tafsir",
            "fields": {"name": "تفسير"},
            "slug_for": {"name_ar": "تفسير"},
        }

        # Act
        with patch.object(
            GeminiClient, GeminiClient.generate_json.__name__, return_value={"name": "Tafsir", "slug_words": ["!!"]}
        ):
            response = self.client.post(URL, data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNone(response.json()["slug"])

    def test_ai_translate_where_no_fields_and_no_slug_names_should_return_400_ai_translate_empty(self):
        # Arrange
        self.authenticate_user(self._admin())

        # Act
        with patch.object(GeminiClient, GeminiClient.generate_json.__name__) as ai:
            response = self.client.post(
                URL,
                data={"mode": "translate", "category": "tafsir", "fields": {}, "slug_for": {"name_ar": " "}},
                content_type="application/json",
            )

        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("ai_translate_empty", response.json()["error_name"])
        ai.assert_not_called()

    def test_ai_translate_where_category_is_reciter_should_ignore_slug_for(self):
        # Arrange
        self.authenticate_user(self._admin(PermissionChoice.PORTAL_CREATE_RECITER))
        payload = {
            "mode": "translate",
            "category": "reciter",
            "fields": {"name": "مشاري العفاسي"},
            "slug_for": {"name_ar": "مشاري العفاسي"},
        }

        # Act
        with patch.object(
            GeminiClient, GeminiClient.generate_json.__name__, return_value={"name": "Mishary Alafasy"}
        ) as ai:
            response = self.client.post(URL, data=payload, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNone(response.json()["slug"])
        self.assertNotIn("slug_words", ai.call_args.kwargs["schema"]["properties"])

    def test_ai_slug_endpoint_where_called_should_no_longer_exist(self):
        # Arrange
        self.authenticate_user(self._admin())

        # Act
        response = self.client.post("/portal/ai/slug/", data={"category": "tafsir"}, content_type="application/json")

        # Assert
        self.assertEqual(404, response.status_code)
