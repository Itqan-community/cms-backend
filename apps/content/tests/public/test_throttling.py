"""Tests for the enforced global per-client throttling on the public
``developers_api`` (see apps/core/ninja_utils/throttle.py and
config/developers_api.py)."""

from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpRequest

from apps.core.ninja_utils.throttle import PublicApiAnonRateThrottle, PublicApiUserRateThrottle
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


def _make_request(*, user, remote_addr: str = "10.0.0.1") -> HttpRequest:
    request = HttpRequest()
    request.user = user
    request.META["REMOTE_ADDR"] = remote_addr
    request.path = "/reciters/"
    return request


class PublicApiUserRateThrottleTest(BaseTestCase):
    def test_get_cache_key_where_user_authenticated_should_key_on_user_pk_without_path(self):
        # Arrange
        cache.clear()
        user = User.objects.create_user(email="t@example.com", name="T")
        throttle = PublicApiUserRateThrottle()
        request = _make_request(user=user)

        # Act
        key = throttle.get_cache_key(request)

        # Assert: keyed on the user pk and NOT scoped by request.path (global budget).
        self.assertEqual(throttle.cache_format % {"scope": "public_user", "ident": user.pk}, key)
        self.assertNotIn(request.path, key)

    def test_get_cache_key_where_user_anonymous_should_return_none(self):
        # Arrange
        throttle = PublicApiUserRateThrottle()
        request = _make_request(user=AnonymousUser())

        # Act
        key = throttle.get_cache_key(request)

        # Assert: anonymous traffic is not handled by the user throttle.
        self.assertIsNone(key)

    def test_allow_request_where_budget_exceeded_should_block(self):
        # Arrange
        cache.clear()
        user = User.objects.create_user(email="t2@example.com", name="T2")
        throttle = PublicApiUserRateThrottle()
        throttle.num_requests = 2
        throttle.duration = 60
        request = _make_request(user=user)

        # Act
        first = throttle.allow_request(request)
        second = throttle.allow_request(request)
        third = throttle.allow_request(request)

        # Assert: third request over a budget of 2 is blocked.
        self.assertTrue(first)
        self.assertTrue(second)
        self.assertFalse(third)

    def test_allow_request_where_different_users_should_have_independent_budgets(self):
        # Arrange
        cache.clear()
        user_a = User.objects.create_user(email="a@example.com", name="A")
        user_b = User.objects.create_user(email="b@example.com", name="B")
        throttle = PublicApiUserRateThrottle()
        throttle.num_requests = 1
        throttle.duration = 60

        # Act: exhaust user_a's budget, then user_b makes a request.
        throttle.allow_request(_make_request(user=user_a))
        user_a_blocked = throttle.allow_request(_make_request(user=user_a))
        user_b_allowed = throttle.allow_request(_make_request(user=user_b))

        # Assert: user_b is unaffected by user_a hitting the limit.
        self.assertFalse(user_a_blocked)
        self.assertTrue(user_b_allowed)


class PublicApiAnonRateThrottleTest(BaseTestCase):
    def test_get_cache_key_where_user_anonymous_should_key_on_ip(self):
        # Arrange
        throttle = PublicApiAnonRateThrottle()
        request = _make_request(user=AnonymousUser(), remote_addr="203.0.113.7")

        # Act
        key = throttle.get_cache_key(request)

        # Assert
        self.assertEqual(throttle.cache_format % {"scope": "public_anon", "ident": "203.0.113.7"}, key)

    def test_get_cache_key_where_user_authenticated_should_return_none(self):
        # Arrange
        user = User.objects.create_user(email="auth@example.com", name="Auth")
        throttle = PublicApiAnonRateThrottle()
        request = _make_request(user=user)

        # Act
        key = throttle.get_cache_key(request)

        # Assert: authenticated clients are handled by the user throttle, not here.
        self.assertIsNone(key)

    def test_allow_request_where_different_ips_should_have_independent_budgets(self):
        # Arrange
        cache.clear()
        throttle = PublicApiAnonRateThrottle()
        throttle.num_requests = 1
        throttle.duration = 60

        # Act
        throttle.allow_request(_make_request(user=AnonymousUser(), remote_addr="1.1.1.1"))
        ip1_blocked = throttle.allow_request(_make_request(user=AnonymousUser(), remote_addr="1.1.1.1"))
        ip2_allowed = throttle.allow_request(_make_request(user=AnonymousUser(), remote_addr="2.2.2.2"))

        # Assert
        self.assertFalse(ip1_blocked)
        self.assertTrue(ip2_allowed)


class PublicApiThrottleEndpointTest(BaseTestCase):
    """Integration: a real public endpoint returns 429 in the standard error
    shape once the per-client budget is exhausted."""

    def test_public_endpoint_where_rate_exceeded_should_return_429_in_standard_shape(self):
        # Arrange
        from config.developers_api import developers_api

        cache.clear()
        # The developers_api is configured with [PublicApiUserRateThrottle,
        # PublicApiAnonRateThrottle]; in the test settings traffic resolves as
        # anonymous, so shrink the anon throttle's budget to 1.
        anon_throttle = next(t for t in developers_api.throttle if isinstance(t, PublicApiAnonRateThrottle))

        # Act
        with patch.object(anon_throttle, "num_requests", 1), patch.object(anon_throttle, "duration", 60):
            first = self.client.get("/reciters/")
            second = self.client.get("/reciters/")

        # Assert
        self.assertEqual(200, first.status_code, first.content)
        self.assertEqual(429, second.status_code, second.content)
        self.assertEqual("throttled", second.json()["error_name"])
        self.assertIn("Retry-After", second)
