from django.conf import settings
from django.core.cache import cache
from model_bakery import baker
import pytest

from apps.core.tests.base import BaseTestCase
from apps.users.models import User


@pytest.mark.skipif(condition=not settings.MIXPANEL_ENABLED, reason="old flow before allauth")
class TestGetUsageBoardUrl(BaseTestCase):
    URL = "/portal/usage/board-url/"

    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = User.objects.create_user(email="user@test.com", password="x")

    def _get(self, publisher: Publisher | None):
        self.authenticate_user(self.user)
        headers = {"HTTP_X_TENANT": str(publisher.id)} if publisher else {}
        return self.client.get(self.URL, **headers)

    def test_returns_board_url_of_publisher_in_request(self):
        publisher = baker.make(Publisher, mixpanel_board_url="https://eu.mixpanel.com/public/BOARD123")

        resp = self._get(publisher)

        assert resp.status_code == 200, resp.content
        assert resp.json()["board_url"] == "https://eu.mixpanel.com/public/BOARD123"

    def test_returns_empty_when_publisher_has_no_board_url(self):
        publisher = baker.make(Publisher, mixpanel_board_url="")

        resp = self._get(publisher)

        assert resp.status_code == 200, resp.content
        self.assertEqual("", resp.json()["board_url"])

    def test_returns_null_when_no_publisher_in_request(self):
        resp = self._get(None)

        assert resp.status_code == 200, resp.content
        self.assertIsNone(resp.json()["board_url"])

    def test_unauthenticated_returns_401(self):
        self.authenticate_user(None)

        resp = self.client.get(self.URL)

        assert resp.status_code == 401
