from django.conf import settings
import pytest

from apps.core.tests import BaseTestCase
from apps.users.models import User


@pytest.mark.skipif(condition=not settings.MIXPANEL_ENABLED, reason="old flow before allauth")
class TestGetUsageBoardUrl(BaseTestCase):
    URL = "/portal/usage/board-url/"

    def test_authenticated_user_returns_main_board_url(self):
        with self.settings(MIXPANEL_MAIN_BOARD_URL="https://eu.mixpanel.com/public/BOARD123"):
            user = User.objects.create_user(email="user@test.com", password="x")
            self.authenticate_user(user)

            resp = self.client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["board_url"] == "https://eu.mixpanel.com/public/BOARD123"

    def test_returns_null_when_main_board_url_not_set(self):
        with self.settings(MIXPANEL_MAIN_BOARD_URL=""):
            user = User.objects.create_user(email="user2@test.com", password="x")
            self.authenticate_user(user)

            resp = self.client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["board_url"] is None

    def test_unauthenticated_returns_401(self):
        self.authenticate_user(None)

        resp = self.client.get(self.URL)

        assert resp.status_code == 401
