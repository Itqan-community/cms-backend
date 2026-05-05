from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, StreamingHttpResponse
from django.test import RequestFactory

from apps.usage_tracking.middlewares.usage_tracking_middleware import (
    UsageTrackingMiddleware,
    _classify_path,
    _client_ip,
    _detect_auth_method,
    _extract_error_code,
    _parse_query_params,
    _resolve_application,
)


class _Resp(HttpResponse):
    pass


def _make_middleware(response_body=b'[{"id": 1}, {"id": 2}]', status=200):
    def get_response(request):
        return _Resp(content=response_body, status=status, content_type="application/json")

    return UsageTrackingMiddleware(get_response)


class TestUsageTrackingMiddleware:
    def setup_method(self):
        self.factory = RequestFactory()

    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.track_api_request_task")
    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.resolve_publisher_from_request")
    def test_tracked_path_dispatches_celery_task(self, mock_resolve, mock_task):
        mock_resolve.return_value = (42, "acme", "Acme Publisher")
        mw = _make_middleware()
        request = self.factory.get("/reciters")
        request.access_token = SimpleNamespace(id=7, user=SimpleNamespace(id=99))

        mw(request)

        assert mock_task.delay.called
        _, kwargs = mock_task.delay.call_args
        assert kwargs["event"] == "public_api_request"
        props = kwargs["properties"]
        assert props["publisher_id"] == 42
        assert props["publisher_slug"] == "acme"
        assert props["publisher_name"] == "Acme Publisher"
        assert props["endpoint"] == "GET /reciters"
        assert props["status_code"] == 200
        assert "latency_ms" in props
        assert props["entity_ids"] == [1, 2]
        assert "method" in props
        assert "path" in props
        assert "entity_names" in props
        assert "entity_type" in props
        assert "accessed_entity_id" in props
        assert "query_string" in props
        assert "application_id" in props
        assert "application_name" in props
        assert "auth_method" in props
        assert "user_agent" in props
        assert "error_code" in props

    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.track_api_request_task")
    def test_excluded_path_portal_skipped(self, mock_task):
        mw = _make_middleware()
        request = self.factory.get("/portal/stats")

        mw(request)

        mock_task.delay.assert_not_called()

    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.track_api_request_task")
    def test_excluded_path_admin_skipped(self, mock_task):
        mw = _make_middleware()
        request = self.factory.get("/django-admin/")

        mw(request)

        mock_task.delay.assert_not_called()

    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.track_api_request_task")
    def test_excluded_path_oauth_skipped(self, mock_task):
        mw = _make_middleware()
        request = self.factory.get("/o/token/")

        mw(request)

        mock_task.delay.assert_not_called()

    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.track_api_request_task")
    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.resolve_publisher_from_request")
    def test_unauthenticated_request_still_tracked_with_anon(self, mock_resolve, mock_task):
        mock_resolve.return_value = (None, None, None)
        mw = _make_middleware()
        request = self.factory.get("/reciters")

        mw(request)

        assert mock_task.delay.called
        _, kwargs = mock_task.delay.call_args
        assert kwargs["distinct_id"].startswith("anon-")
        assert kwargs["properties"]["publisher_id"] is None

    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.track_api_request_task")
    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.resolve_publisher_from_request")
    def test_celery_dispatch_failure_does_not_break_request(self, mock_resolve, mock_task):
        mock_resolve.return_value = (42, "acme", "Acme Publisher")
        mock_task.delay.side_effect = RuntimeError("broker down")
        mw = _make_middleware()
        request = self.factory.get("/reciters")

        response = mw(request)

        assert response.status_code == 200

    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.track_api_request_task")
    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.resolve_publisher_from_request")
    def test_streaming_response_is_not_buffered(self, mock_resolve, mock_task):
        mock_resolve.return_value = (42, "acme", "Acme Publisher")

        def get_response(request):
            return StreamingHttpResponse(iter([b"chunk1", b"chunk2"]), status=200)

        mw = UsageTrackingMiddleware(get_response)
        request = self.factory.get("/reciters")

        response = mw(request)

        assert response.streaming is True
        assert mock_task.delay.called
        _, kwargs = mock_task.delay.call_args
        assert kwargs["properties"]["entity_ids"] == []

    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.track_api_request_task")
    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.resolve_publisher_from_request")
    def test_distinct_id_uses_user_id_when_authed(self, mock_resolve, mock_task):
        mock_resolve.return_value = (42, "acme", "Acme Publisher")
        mw = _make_middleware()
        request = self.factory.get("/reciters")
        request.user = SimpleNamespace(pk=99, is_authenticated=True)

        mw(request)

        _, kwargs = mock_task.delay.call_args
        assert kwargs["distinct_id"] == "user-99"


class TestClassifyPath:
    def test_recitation_detail(self):
        assert _classify_path("/public-api/v1/recitations/123/") == ("recitation", 123)

    def test_recitation_list(self):
        entity_type, accessed_id = _classify_path("/public-api/v1/recitations/")
        assert entity_type == "recitation"
        assert accessed_id is None

    def test_reciters_list(self):
        entity_type, accessed_id = _classify_path("/public-api/v1/reciters/")
        assert entity_type == "reciter"
        assert accessed_id is None

    def test_riwayahs_list(self):
        entity_type, accessed_id = _classify_path("/public-api/v1/riwayahs/")
        assert entity_type == "riwayah"
        assert accessed_id is None

    def test_unknown_path_returns_none(self):
        assert _classify_path("/portal/stats/") == (None, None)


class TestDistinctId:
    def setup_method(self):
        self.factory = RequestFactory()

    def test_oauth2_client_credentials_uses_app_id(self):
        request = self.factory.get("/reciters/")
        request.user = AnonymousUser()
        request.access_token = SimpleNamespace(application=SimpleNamespace(id=42))

        assert UsageTrackingMiddleware._distinct_id(request) == "app-42"

    def test_jwt_authenticated_uses_user_pk(self):
        request = self.factory.get("/reciters/")
        request.user = SimpleNamespace(pk=99, is_authenticated=True)

        assert UsageTrackingMiddleware._distinct_id(request) == "user-99"

    def test_oauth2_token_takes_precedence_over_user(self):
        request = self.factory.get("/reciters/")
        request.user = SimpleNamespace(pk=99, is_authenticated=True)
        request.access_token = SimpleNamespace(application=SimpleNamespace(id=42))

        assert UsageTrackingMiddleware._distinct_id(request) == "app-42"

    def test_anonymous_falls_back_to_uuid(self):
        request = self.factory.get("/reciters/")
        request.user = AnonymousUser()

        result = UsageTrackingMiddleware._distinct_id(request)

        assert result.startswith("anon-")
        assert len(result) == 17  # "anon-" + 12 hex chars


class TestClassifyPathDetailEndpoints:
    def test_reciter_detail(self):
        assert _classify_path("/reciters/7/") == ("reciter", 7)

    def test_riwayah_detail(self):
        assert _classify_path("/riwayahs/2/") == ("riwayah", 2)


class TestDetectAuthMethod:
    def setup_method(self):
        self.factory = RequestFactory()

    def test_oauth2_when_access_token_set(self):
        request = self.factory.get("/")
        request.access_token = SimpleNamespace()
        request.user = AnonymousUser()
        assert _detect_auth_method(request) == "oauth2"

    def test_jwt_when_bearer_header(self):
        request = self.factory.get("/", HTTP_AUTHORIZATION="Bearer xyz")
        request.user = SimpleNamespace(is_authenticated=True)
        assert _detect_auth_method(request) == "jwt"

    def test_session_when_authed_no_bearer(self):
        request = self.factory.get("/")
        request.user = SimpleNamespace(is_authenticated=True)
        assert _detect_auth_method(request) == "session"

    def test_anonymous_when_unauthed(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        assert _detect_auth_method(request) == "anonymous"


class TestParseQueryParams:
    def test_empty_returns_empty(self):
        assert _parse_query_params("") == {}

    def test_extracts_page(self):
        assert _parse_query_params("page=3") == {"page": 3}

    def test_extracts_search(self):
        assert _parse_query_params("search=mashary") == {"search": "mashary"}

    def test_extracts_filters_as_int(self):
        result = _parse_query_params("reciter_id=6&riwayah_id=2")
        assert result == {"filter_reciter_id": 6, "filter_riwayah_id": 2}

    def test_extracts_ordering(self):
        assert _parse_query_params("ordering=-name") == {"ordering": "-name"}

    def test_combined(self):
        result = _parse_query_params("page=2&search=hafs&reciter_id=6&ordering=name")
        assert result == {
            "page": 2,
            "search": "hafs",
            "filter_reciter_id": 6,
            "ordering": "name",
        }

    def test_invalid_page_skipped(self):
        assert _parse_query_params("page=abc") == {}


class TestExtractErrorCode:
    def test_2xx_returns_none(self):
        resp = HttpResponse(b'{"error_name": "should_be_ignored"}', status=200)
        assert _extract_error_code(resp) is None

    def test_4xx_with_error_name_extracts(self):
        resp = HttpResponse(b'{"error_name": "validation_failed", "message": "bad"}', status=400)
        assert _extract_error_code(resp) == "validation_failed"

    def test_4xx_without_error_name_returns_none(self):
        resp = HttpResponse(b'{"foo": "bar"}', status=400)
        assert _extract_error_code(resp) is None

    def test_streaming_returns_none(self):
        resp = StreamingHttpResponse(iter([b"chunk"]), status=400)
        assert _extract_error_code(resp) is None


class TestResolveApplication:
    def test_no_token_returns_none_pair(self):
        request = SimpleNamespace()
        assert _resolve_application(request) == (None, None)

    def test_token_with_application(self):
        request = SimpleNamespace(access_token=SimpleNamespace(application=SimpleNamespace(id=7, name="my-app")))
        assert _resolve_application(request) == (7, "my-app")


class TestClientIp:
    def setup_method(self):
        self.factory = RequestFactory()

    def test_xff_first_entry_wins(self):
        request = self.factory.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8")
        assert _client_ip(request) == "1.2.3.4"

    def test_falls_back_to_remote_addr(self):
        request = self.factory.get("/", REMOTE_ADDR="9.9.9.9")
        assert _client_ip(request) == "9.9.9.9"

    def test_returns_none_when_neither_present(self):
        request = self.factory.get("/")
        request.META.pop("REMOTE_ADDR", None)
        assert _client_ip(request) is None
