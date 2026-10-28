from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.api.portal import quran_range
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.tests.services.test_effective_permissions import role
from apps.users.models import User

URL = "/portal/content/quran-range/"


class QuranRangeApiTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_group_quran()
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)

    def _reader(self) -> None:
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)

    def test_quran_range_where_word_range_crosses_ayah_should_return_words_in_order(self):
        # Arrange
        self._reader()

        # Act
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                URL,
                {"from_surah": 1, "from_ayah": 1, "from_word": 3, "to_surah": 1, "to_ayah": 2, "to_word": 2},
            )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json(),
            {
                "units": [
                    {"surah": 1, "ayah": 1, "word": 3, "text": "w3"},
                    {"surah": 1, "ayah": 2, "word": 1, "text": "w4"},
                    {"surah": 1, "ayah": 2, "word": 2, "text": "w5"},
                ],
                "truncated": False,
            },
        )
        quran_queries = [q for q in queries.captured_queries if "quran_" in q["sql"]]
        self.assertLessEqual(len(quran_queries), 2)

    def test_quran_range_where_tafsir_read_comes_from_publisher_role_should_return_200(self):
        # Arrange
        publisher = baker.make(Publisher)
        member = User.objects.create_user(email="role-reader@example.com", name="Role Reader")
        PublisherMember.objects.create(
            user=member,
            publisher=publisher,
            group=role(publisher, PermissionChoice.PORTAL_ACCESS, PermissionChoice.PORTAL_READ_TAFSIR),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.authenticate_user(member, HTTP_X_TENANT=str(publisher.id))

        # Act
        response = self.client.get(URL, {"from_surah": 1, "from_ayah": 3, "to_surah": 2, "to_ayah": 1})

        # Assert
        self.assertEqual(response.status_code, 200, response.content)

    def test_quran_range_where_ayah_range_should_return_ayahs(self):
        # Arrange
        self._reader()

        # Act
        response = self.client.get(URL, {"from_surah": 1, "from_ayah": 3, "to_surah": 2, "to_ayah": 1})

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json()["units"],
            [{"surah": 1, "ayah": 3, "word": None, "text": "a3"}, {"surah": 2, "ayah": 1, "word": None, "text": "a4"}],
        )

    def test_quran_range_where_over_limit_should_truncate(self):
        # Arrange
        self._reader()

        # Act
        with patch.object(quran_range, "QURAN_RANGE_LIMIT", 2):
            response = self.client.get(URL, {"from_surah": 1, "from_ayah": 1, "to_surah": 2, "to_ayah": 2})

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual([unit["ayah"] for unit in body["units"]], [1, 2])
        self.assertTrue(body["truncated"])

    def test_quran_range_where_reversed_should_return_400(self):
        # Arrange
        self._reader()

        # Act
        response = self.client.get(URL, {"from_surah": 2, "from_ayah": 1, "to_surah": 1, "to_ayah": 1})

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "group_range_invalid")

    def test_quran_range_where_no_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(URL, {"from_surah": 1, "from_ayah": 1, "to_surah": 1, "to_ayah": 2})

        # Assert
        self.assertEqual(response.status_code, 403, response.content)
