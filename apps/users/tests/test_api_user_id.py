from uuid import uuid4

from django.test import override_settings
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.users.models import APIKey, User


@override_settings(ENABLE_API_KEY_AUTH=True)
class PublicApiUserIdHeaderTestCase(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = baker.make(User)

    def _make_request(self, value):
        unique_name = f"User ID Key {uuid4().hex}"
        _, raw_key = APIKey.objects.create_key(name=unique_name, user=self.user)
        return self.client.get(
            "/recitations/",
            headers={"x-api-key": raw_key, "X-Itqan-User-Id": value},
        )

    def test_public_api_accepts_valid_itqan_user_id_header(self):
        for valid_value in [
            "user-123",
            "USER_123",
            "abc.def",
            "abc:def",
            "abc123",
            "a" * 64,
            " user-123 ",
        ]:
            with self.subTest(valid_value=valid_value):
                res = self._make_request(valid_value)
                self.assertEqual(200, res.status_code, res.content)
                self.assertEqual(valid_value.strip(), res.wsgi_request.itqan_user_id)

    def test_public_api_rejects_empty_and_blank_values_with_422(self):
        for invalid_value in ["", " ", "\t", "\n", "   \n  "]:
            with self.subTest(invalid_value=repr(invalid_value)):
                res = self._make_request(invalid_value)
                self.assertEqual(422, res.status_code, res.content)
                self.assertEqual("invalid_itqan_user_id", res.json()["error_name"])

    def test_public_api_rejects_invalid_character_sets_with_422(self):
        for invalid_value in [
            "user id",
            "user/id",
            "user@id",
            "user+id",
            "user,id",
            "user\\id",
            "user\nname",
            "user\tname",
            "éxample",
            "مرحبا",
            "user?name",
        ]:
            with self.subTest(invalid_value=invalid_value):
                res = self._make_request(invalid_value)
                self.assertEqual(422, res.status_code, res.content)
                self.assertEqual("invalid_itqan_user_id", res.json()["error_name"])

    def test_public_api_rejects_values_starting_with_non_alphanumeric_character_with_422(self):
        for invalid_value in [
            ".user",
            "_user",
            "-user",
            ":user",
            "'user",
            '"user',
        ]:
            with self.subTest(invalid_value=invalid_value):
                res = self._make_request(invalid_value)
                self.assertEqual(422, res.status_code, res.content)
                self.assertEqual("invalid_itqan_user_id", res.json()["error_name"])

    def test_public_api_rejects_values_longer_than_64_characters_with_422(self):
        res = self._make_request("a" * 65)

        self.assertEqual(422, res.status_code, res.content)
        self.assertEqual("invalid_itqan_user_id", res.json()["error_name"])

    def test_same_itqan_user_id_is_namespaced_by_api_key_owner(self):
        user_a = baker.make(User)
        user_b = baker.make(User)
        _, raw_key_a = APIKey.objects.create_key(name="App A", user=user_a)
        _, raw_key_b = APIKey.objects.create_key(name="App B", user=user_b)

        res_a = self.client.get(
            "/recitations/",
            headers={"x-api-key": raw_key_a, "X-Itqan-User-Id": "same-user-id"},
        )
        res_b = self.client.get(
            "/recitations/",
            headers={"x-api-key": raw_key_b, "X-Itqan-User-Id": "same-user-id"},
        )

        self.assertEqual("same-user-id", res_a.wsgi_request.itqan_user_id)
        self.assertEqual("same-user-id", res_b.wsgi_request.itqan_user_id)
        self.assertNotEqual(res_a.wsgi_request.user.pk, res_b.wsgi_request.user.pk)
