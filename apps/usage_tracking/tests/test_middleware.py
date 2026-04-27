from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse, StreamingHttpResponse
from django.test import RequestFactory

from apps.usage_tracking.middlewares.usage_tracking_middleware import UsageTrackingMiddleware


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
        mock_resolve.return_value = (42, "acme")
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
        assert props["endpoint"] == "GET /reciters"
        assert props["status_code"] == 200
        assert "latency_ms" in props
        assert props["entity_ids"] == [1, 2]

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
        mock_resolve.return_value = (None, None)
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
        mock_resolve.return_value = (42, "acme")
        mock_task.delay.side_effect = RuntimeError("broker down")
        mw = _make_middleware()
        request = self.factory.get("/reciters")

        response = mw(request)

        assert response.status_code == 200

    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.track_api_request_task")
    @patch("apps.usage_tracking.middlewares.usage_tracking_middleware.resolve_publisher_from_request")
    def test_streaming_response_is_not_buffered(self, mock_resolve, mock_task):
        mock_resolve.return_value = (42, "acme")

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
    @patch(
        "apps.usage_tracking.middlewares.usage_tracking_middleware.resolve_publisher_from_request"
    )
    def test_distinct_id_uses_user_id_when_authed(self, mock_resolve, mock_task):
        mock_resolve.return_value = (42, "acme")
        mw = _make_middleware()
        request = self.factory.get("/reciters")
        request.user = SimpleNamespace(pk=99, is_authenticated=True)

        mw(request)

        _, kwargs = mock_task.delay.call_args
        assert kwargs["distinct_id"] == "user-99"
