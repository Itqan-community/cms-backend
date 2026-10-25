"""The log-only ``NinjaUserPathRateThrottle``: reports bursts of the same request
from our web app, never blocks."""

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.http import HttpRequest

from apps.core.ninja_utils import throttle as throttle_module
from apps.core.ninja_utils.throttle import NinjaUserPathRateThrottle
from apps.core.tests.base import BaseTestCase


def _make_request(**headers: str) -> HttpRequest:
    request = HttpRequest()
    request.user = AnonymousUser()
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    request.META.update(headers)
    request.path = "/cms-api/assets/"
    return request


def _burst(request: HttpRequest) -> list[bool]:
    throttle = NinjaUserPathRateThrottle()
    throttle.num_requests = 1
    throttle.duration = 60
    return [throttle.allow_request(request) for _ in range(2)]


class NinjaUserPathRateThrottleTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_allow_request_where_browser_page_repeats_request_should_log_error_and_allow(self):
        # Arrange
        request = _make_request(HTTP_ORIGIN="https://cms.itqan.dev")

        # Act
        with self.assertLogs(throttle_module.logger, level="ERROR") as logs:
            allowed = _burst(request)

        # Assert
        self.assertEqual([True, True], allowed)
        self.assertIn("UserPathRateThrottle error for", logs.output[0])

    def test_allow_request_where_page_sends_only_referer_should_log_error(self):
        # Arrange
        request = _make_request(HTTP_REFERER="https://staging.cms.itqan.dev/gallery")

        # Act
        with self.assertLogs(throttle_module.logger, level="ERROR") as logs:
            _burst(request)

        # Assert
        self.assertEqual(1, len(logs.output))

    def test_allow_request_where_server_side_client_repeats_request_should_allow_without_logging(self):
        # Arrange — a server (here another site's Cloudflare Worker) sends no Origin or Referer
        request = _make_request(HTTP_CF_WORKER="example.pages.dev", HTTP_USER_AGENT="Next.js Middleware")

        # Act
        with self.assertNoLogs(throttle_module.logger, level="ERROR"):
            allowed = _burst(request)

        # Assert
        self.assertEqual([True, True], allowed)
