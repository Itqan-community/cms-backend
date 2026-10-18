import json

from django.conf import settings
from django.test import override_settings
import httpx

from apps.core.gemini import (
    GeminiClient,
    GeminiError,
    GeminiQuotaExceeded,
    GeminiRateLimited,
    GeminiUnavailable,
)
from apps.core.tests.base import BaseTestCase


def _client(handler) -> GeminiClient:
    return GeminiClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def _quota_error(quota_id: str) -> dict:
    violation = {"quotaMetric": "generativelanguage.googleapis.com/generate_requests", "quotaId": quota_id}
    return {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [violation]},
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "35s"},
            ],
        }
    }


def _ok(text: str) -> httpx.Response:
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


@override_settings(GEMINI_API_KEY="test-key", GEMINI_FAST_MODEL="fast-model")
class GeminiClientTests(BaseTestCase):
    def test_generate_json_where_response_ok_should_return_parsed_dict(self):
        # Arrange
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["key"] = request.headers["x-goog-api-key"]
            seen["body"] = json.loads(request.content)
            return _ok('{"name": "Tafsir Ibn Kathir"}')

        # Act
        result = _client(handler).generate_json(system="sys", prompt="p", schema={"type": "OBJECT"})

        # Assert
        self.assertEqual(result, {"name": "Tafsir Ibn Kathir"})
        self.assertIn("/models/fast-model:generateContent", seen["url"])
        self.assertEqual(seen["key"], "test-key")
        self.assertEqual(seen["body"]["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(seen["body"]["generationConfig"]["responseSchema"], {"type": "OBJECT"})

    def test_generate_json_where_429_per_day_quota_should_raise_quota_exceeded(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json=_quota_error("GenerateRequestsPerDayPerProjectPerModel-FreeTier"))

        # Act / Assert
        with self.assertRaises(GeminiQuotaExceeded):
            _client(handler).generate_json(system="s", prompt="p", schema={})

    def test_generate_json_where_429_per_minute_quota_should_raise_rate_limited(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json=_quota_error("GenerateRequestsPerMinutePerProjectPerModel-FreeTier"))

        # Act
        with self.assertRaises(GeminiRateLimited) as ctx:
            _client(handler).generate_json(system="s", prompt="p", schema={})

        # Assert
        self.assertNotIsInstance(ctx.exception, GeminiQuotaExceeded)

    def test_generate_json_where_429_without_details_should_raise_rate_limited(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="Too many requests")

        # Act / Assert
        with self.assertRaises(GeminiRateLimited):
            _client(handler).generate_json(system="s", prompt="p", schema={})

    def test_generate_json_where_status_500_should_raise_unavailable(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={})

        # Act / Assert
        with self.assertRaises(GeminiUnavailable):
            _client(handler).generate_json(system="s", prompt="p", schema={})

    def test_generate_json_where_timeout_should_raise_unavailable(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("slow", request=request)

        # Act / Assert
        with self.assertRaises(GeminiUnavailable):
            _client(handler).generate_json(system="s", prompt="p", schema={})

    def test_generate_json_where_text_not_json_should_raise_gemini_error(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            return _ok("not json")

        # Act / Assert
        with self.assertRaises(GeminiError):
            _client(handler).generate_json(system="s", prompt="p", schema={})

    def test_generate_json_where_no_candidates_should_raise_gemini_error(self):
        # Arrange
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"candidates": []})

        # Act / Assert
        with self.assertRaises(GeminiError):
            _client(handler).generate_json(system="s", prompt="p", schema={})

    @override_settings(GEMINI_API_KEY="")
    def test_generate_json_where_key_missing_should_raise_unavailable_without_http(self):
        # Arrange
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return _ok("{}")

        # Act / Assert
        with self.assertRaises(GeminiUnavailable):
            _client(handler).generate_json(system="s", prompt="p", schema={})
        self.assertEqual(calls, [])


class BaseTestCaseIsolationTests(BaseTestCase):
    def test_base_test_case_where_env_sets_gemini_key_should_blank_it(self):
        # Arrange / Act
        key = settings.GEMINI_API_KEY

        # Assert
        self.assertEqual("", key)
