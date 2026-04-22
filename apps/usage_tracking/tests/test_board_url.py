from django.conf import settings
import pytest

from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


@pytest.mark.skipif(condition=not settings.MIXPANEL_ENABLED, reason="old flow before allauth")
class TestGetUsageBoardUrl(BaseTestCase):
    URL = "/portal/usage/board-url/"

    def test_staff_returns_main_board_url(self):
        with self.settings(MIXPANEL_MAIN_BOARD_URL="https://eu.mixpanel.com/public/STAFF123"):
            staff = User.objects.create_user(email="staff@test.com", password="x", is_staff=True)
            self.authenticate_user(staff)

            resp = self.client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["board_url"] == "https://eu.mixpanel.com/public/STAFF123"

    def test_staff_returns_null_when_main_board_url_not_set(self):
        with self.settings(MIXPANEL_MAIN_BOARD_URL=""):
            staff = User.objects.create_user(email="staff2@test.com", password="x", is_staff=True)
            self.authenticate_user(staff)

            resp = self.client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["board_url"] is None

    def test_publisher_member_returns_their_board_url(self):
        user = User.objects.create_user(email="pub@test.com", password="x")
        publisher = Publisher.objects.create(
            name="Test Pub",
            mixpanel_board_url="https://eu.mixpanel.com/public/PUB456",
        )
        PublisherMember.objects.create(publisher=publisher, user=user, role="owner")
        self.authenticate_user(user)

        resp = self.client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["board_url"] == "https://eu.mixpanel.com/public/PUB456"

    def test_publisher_member_null_url_returns_null(self):
        user = User.objects.create_user(email="pub2@test.com", password="x")
        publisher = Publisher.objects.create(name="Test Pub 2")
        PublisherMember.objects.create(publisher=publisher, user=user, role="owner")
        self.authenticate_user(user)

        resp = self.client.get(self.URL)

        assert resp.status_code == 200
        assert resp.json()["board_url"] is None

    def test_unauthenticated_returns_401(self):
        self.authenticate_user(None)

        resp = self.client.get(self.URL)

        assert resp.status_code == 401

    def test_no_membership_returns_403(self):
        user = User.objects.create_user(email="nomember@test.com", password="x")
        self.authenticate_user(user)

        resp = self.client.get(self.URL)

        assert resp.status_code == 403

    def test_staff_with_publisher_id_returns_publisher_board_url(self):
        staff = User.objects.create_user(email="staff3@test.com", password="x", is_staff=True)
        publisher = Publisher.objects.create(
            name="Pub For Staff",
            mixpanel_board_url="https://eu.mixpanel.com/public/PUB789",
        )
        self.authenticate_user(staff)

        resp = self.client.get(self.URL, {"publisher_id": publisher.pk})

        assert resp.status_code == 200
        assert resp.json()["board_url"] == "https://eu.mixpanel.com/public/PUB789"

    def test_staff_with_invalid_publisher_id_returns_404(self):
        staff = User.objects.create_user(email="staff4@test.com", password="x", is_staff=True)
        self.authenticate_user(staff)

        resp = self.client.get(self.URL, {"publisher_id": 99999})

        assert resp.status_code == 404
