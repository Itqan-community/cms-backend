from datetime import UTC, date, datetime
import itertools

from django.core.cache import cache

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import TrafficDaily, TrafficEvent, UsageApp
from apps.users.models import User

BASE = "/cms-api/developers/usage"
RANGE = "start_date=2026-10-10&end_date=2026-10-16"
_ray = itertools.count(1)


def daily(day: date, **values) -> TrafficDaily:
    row = {"kind": "api_call", "country": "SA", "channel": "app_identified", "platform": "server", "sessions": 0}
    row.update(values)
    return TrafficDaily.objects.create(day=day, **row)


def event(listener: str, **values) -> TrafficEvent:
    row = {
        "kind": "api_call",
        "country": "SA",
        "channel": "app_identified",
        "platform": "server",
        "status_class": "full",
        "ua_family": "okhttp",
        "occurred_at": datetime(2026, 10, 12, 9, tzinfo=UTC),
    }
    row.update(values)
    return TrafficEvent.objects.create(ray_id=f"d{next(_ray)}", listener_id=listener, **row)


class TestDeveloperUsageReports(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = User.objects.create_user(email="dev@example.com", name="Dev")
        self.other_user = User.objects.create_user(email="other@example.com", name="Other")
        self.app = UsageApp.objects.create(user=self.user, name="My App", slug="my-app")
        self.other_app = UsageApp.objects.create(user=self.other_user, name="Their App", slug="their-app")
        daily(date(2026, 10, 12), app_id=self.app.id, sessions=40, endpoint="/recitations/{id}/")
        daily(date(2026, 10, 12), app_id=self.app.id, sessions=2, endpoint="/tafsirs/", country="EG")
        daily(date(2026, 10, 12), app_id=self.other_app.id, sessions=500, endpoint="/recitations/{id}/")
        for listener in ("L1", "L2", "L3"):
            event(listener, app_id=self.app.id, endpoint="/recitations/{id}/", end_user_id=f"U-{listener}")
        event("L9", app_id=self.app.id, endpoint="/tafsirs/", country="EG")

    def test_summary_where_anonymous_should_return_401(self):
        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_error", response.json()["error_name"])

    def test_summary_where_signed_in_should_count_own_apps_only(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        metrics = response.json()["metrics"]
        assert metrics["api_calls"]["value"] == 42
        assert metrics["unique_end_users"]["value"] == 3

    def test_summary_where_other_users_app_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}&app={self.other_app.id}")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("app_not_found", response.json()["error_name"])

    def test_summary_where_user_has_no_apps_should_return_zeros(self):
        # Arrange
        self.authenticate_user(User.objects.create_user(email="new@example.com", name="New"))

        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["metrics"]["api_calls"]["value"] == 0

    def test_breakdown_where_by_endpoint_should_apply_privacy_floor(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{BASE}/breakdown/?{RANGE}&metric=api_calls&by=endpoint")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        assert body["items"] == [
            {"key": "/recitations/{id}/", "label": None, "value": 40, "previous": None},
            {"key": "/tafsirs/", "label": None, "value": "<3", "previous": None},
        ]
        assert body["other"] is None

    def test_breakdown_where_privacy_floor_applies_should_hide_the_total(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{BASE}/breakdown/?{RANGE}&metric=api_calls&by=endpoint")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["total"] is None

    def test_breakdown_where_previous_period_is_below_the_floor_should_hide_it(self):
        # Arrange: one listener called /recitations/{id}/ in the previous week.
        daily(date(2026, 10, 5), app_id=self.app.id, sessions=1, endpoint="/recitations/{id}/")
        event("P1", app_id=self.app.id, endpoint="/recitations/{id}/", occurred_at=datetime(2026, 10, 5, 9, tzinfo=UTC))
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{BASE}/breakdown/?{RANGE}&metric=api_calls&by=endpoint&compare=previous_period")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        first = response.json()["items"][0]
        assert (first["value"], first["previous"]) == (40, None)

    def test_breakdown_where_by_app_should_label_own_apps(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{BASE}/breakdown/?{RANGE}&metric=api_calls&by=app")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["items"] == [{"key": str(self.app.id), "label": "My App", "value": 42, "previous": None}]

    def test_timeseries_where_signed_in_should_return_own_series(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"{BASE}/timeseries/?{RANGE}&metric=api_calls")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["series"][0]["points"][2] == {"t": "2026-10-12", "value": 42}
