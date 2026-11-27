from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.core.middlewares.public_list_cache import is_public_list_path
from apps.core.tests.base import BaseTestCase
from apps.users.models import APIKey, User


class PublicListCacheMiddlewareTest(BaseTestCase):
    def test_public_list_where_anonymous_should_be_publicly_cacheable_with_etag(self):
        # Arrange
        baker.make("content.Riwayah", name="Hafs")

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("public, max-age=60", response["Cache-Control"])
        self.assertTrue(response["ETag"].startswith('"'))

    def test_public_list_where_if_none_match_matches_should_return_304_without_body(self):
        # Arrange
        baker.make("content.Riwayah", name="Hafs")
        etag = self.client.get("/riwayahs/")["ETag"]

        # Act
        response = self.client.get("/riwayahs/", headers={"If-None-Match": etag})

        # Assert
        self.assertEqual(304, response.status_code)
        self.assertEqual(b"", response.content)
        self.assertEqual(etag, response["ETag"])
        self.assertEqual("public, max-age=60", response["Cache-Control"])

    def test_public_list_where_if_none_match_is_stale_should_return_200_with_current_etag(self):
        # Arrange: an ETag from an older body
        stale = '"0123456789abcdef"'

        # Act
        response = self.client.get("/riwayahs/", headers={"If-None-Match": stale})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertNotEqual(stale, response["ETag"])

    def test_public_list_where_api_key_sent_should_be_private(self):
        # Arrange
        _, raw_key = APIKey.objects.create_key(name="list-key", user=baker.make(User))

        # Act
        response = self.client.get("/reciters/", headers={"X-API-Key": raw_key})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("private, max-age=60", response["Cache-Control"])
        self.assertIn("ETag", response)

    def test_public_list_where_caching_added_should_not_add_queries(self):
        # Arrange
        self.client.get("/recitations/")

        # Act
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("public, max-age=60", response["Cache-Control"])
        self.assertLessEqual(len(ctx.captured_queries), 3)

    def test_non_list_endpoint_should_keep_its_own_cache_header(self):
        # Arrange / Act
        response = self.client.get("/recitations/999999/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertNotIn("ETag", response)

    def test_is_public_list_path_where_path_given_should_match_only_shared_lists(self):
        # Arrange
        expected = {
            "/recitations/": True,
            "/reciters/": True,
            "/riwayahs/": True,
            "/packages/": True,
            "/recommendations/trending/": True,
            "/recommendations/editorial/": True,
            "/recommendations/similar/12/": True,
            "/recommendations/personalized/": False,
            "/recitations/12/": False,
            "/packages/me/": False,
            "/tenant/recitations/": False,
        }

        # Act
        actual = {path: is_public_list_path(path) for path in expected}

        # Assert
        self.assertEqual(expected, actual)
