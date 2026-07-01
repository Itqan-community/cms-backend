import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from apps.usage_tracking.decorators.track_usage import (
    _client_ip,
    _detect_auth_method,
    _distinct_id,
    _parse_query_params,
    _resolve_application,
    track_extra,
    track_usage,
)
from apps.usage_tracking.tasks import TRACKING_BUFFER_KEY


def _obj(id_, name, publisher_id=None, publisher_name=None):
    publisher = SimpleNamespace(id=publisher_id, name=publisher_name) if publisher_id else None
    return SimpleNamespace(id=id_, name=name, publisher_id=publisher_id, publisher=publisher)


def _mock_redis():
    """Return a mock Redis client and a helper to inspect what was pushed."""
    mock_r = MagicMock()
    mock_get_redis = MagicMock(return_value=mock_r)
    return mock_get_redis, mock_r


def _dispatched_props(mock_r):
    """Parse the JSON payload pushed to the tracking buffer and return its properties."""
    assert mock_r.rpush.called, "expected rpush to be called on Redis mock"
    raw = mock_r.rpush.call_args[0][1]
    return json.loads(raw)["properties"]


class TestTrackUsageDecorator:
    def setup_method(self):
        self.factory = RequestFactory()

    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_paginated_list_extracts_entities_and_publishers(self, mock_get_redis):
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage(entity_type="recitation", publisher_from="publisher")
        def view(request):
            return {
                "results": [
                    _obj(1, "A", publisher_id=10, publisher_name="Pub10"),
                    _obj(2, "B", publisher_id=10, publisher_name="Pub10"),
                    _obj(3, "C", publisher_id=20, publisher_name="Pub20"),
                ],
                "count": 3,
            }

        view(self.factory.get("/recitations/"))

        props = _dispatched_props(mock_r)
        assert props["entity_type"] == "recitation"
        assert props["entity_ids"] == [1, 2, 3]
        assert props["entity_names"] == ["A", "B", "C"]
        assert props["publisher_ids"] == [10, 20]
        assert props["publisher_names"] == ["Pub10", "Pub20"]
        assert props["status_code"] == 200
        assert "latency_ms" in props
        mock_r.rpush.assert_called_once_with(TRACKING_BUFFER_KEY, mock_r.rpush.call_args[0][1])

    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_no_publisher_from_leaves_publishers_empty(self, mock_get_redis):
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage(entity_type="reciter")
        def view(request):
            return {"results": [_obj(1, "Reciter")], "count": 1}

        view(self.factory.get("/reciters/"))

        props = _dispatched_props(mock_r)
        assert props["entity_type"] == "reciter"
        assert props["entity_ids"] == [1]
        assert props["publisher_ids"] == []
        assert props["publisher_names"] == []

    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_track_extra_overrides_auto_extracted(self, mock_get_redis):
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage(entity_type="recitation", publisher_from="publisher")
        def view(request):
            track_extra(
                request,
                entity_ids=[99],
                entity_names=["Asset 99"],
                accessed_entity_name="Asset 99",
                publisher_ids=[7],
                publisher_names=["Owner"],
            )
            return [_obj(1, "track-1"), _obj(2, "track-2")]

        view(self.factory.get("/recitations/99/"))

        props = _dispatched_props(mock_r)
        assert props["entity_ids"] == [99]
        assert props["entity_names"] == ["Asset 99"]
        assert props["accessed_entity_name"] == "Asset 99"
        assert props["publisher_ids"] == [7]

    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_track_extra_merges_across_calls(self, mock_get_redis):
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage()
        def view(request):
            track_extra(request, a=1)
            track_extra(request, b=2)
            return {"results": [], "count": 0}

        view(self.factory.get("/recitations/"))

        props = _dispatched_props(mock_r)
        assert props["a"] == 1
        assert props["b"] == 2

    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_raising_view_does_not_dispatch(self, mock_get_redis):
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage(entity_type="recitation")
        def view(request):
            raise ValueError("boom")

        try:
            view(self.factory.get("/recitations/"))
        except ValueError:
            pass

        mock_r.rpush.assert_not_called()

    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_dispatch_failure_does_not_break_response(self, mock_get_redis):
        mock_r = MagicMock()
        mock_r.rpush.side_effect = RuntimeError("redis down")
        mock_get_redis.return_value = mock_r

        @track_usage()
        def view(request):
            return {"results": [], "count": 0}

        result = view(self.factory.get("/recitations/"))

        assert result == {"results": [], "count": 0}

    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_query_params_captured(self, mock_get_redis):
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage()
        def view(request):
            return {"results": [], "count": 0}

        view(self.factory.get("/recitations/?page=2&search=hafs&riwayah_id=2&ordering=name"))

        props = _dispatched_props(mock_r)
        assert props["page"] == 2
        assert props["search"] == "hafs"
        assert props["filter_riwayah_id"] == 2
        assert props["ordering"] == "name"

    @patch("apps.usage_tracking.decorators.track_usage._resolve_reciter_names", return_value=["Mishary"])
    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_reciter_filter_adds_human_readable_name(self, mock_get_redis, mock_resolve):
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage()
        def view(request):
            return {"results": [], "count": 0}

        view(self.factory.get("/recitations/?reciter_id=6"))

        props = _dispatched_props(mock_r)
        assert props["filter_reciter_id"] == 6
        assert props["filter_reciter_name"] == "Mishary"
        assert props["filter_reciter_names"] == ["Mishary"]
        mock_resolve.assert_called_once_with([6])

    @patch(
        "apps.usage_tracking.decorators.track_usage._resolve_reciter_names",
        return_value=["Mishary", "Saad"],
    )
    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_multiple_reciter_filters_resolve_all_names(self, mock_get_redis, mock_resolve):
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage()
        def view(request):
            return {"results": [], "count": 0}

        view(self.factory.get("/recitations/?reciter_id=6&reciter_id=9"))

        props = _dispatched_props(mock_r)
        assert props["filter_reciter_names"] == ["Mishary", "Saad"]
        assert props["filter_reciter_name"] == "Mishary"
        mock_resolve.assert_called_once_with([6, 9])

    @patch("apps.usage_tracking.decorators.track_usage._resolve_reciter_names")
    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_no_reciter_filter_skips_name_resolution(self, mock_get_redis, mock_resolve):
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage()
        def view(request):
            return {"results": [], "count": 0}

        view(self.factory.get("/recitations/"))

        props = _dispatched_props(mock_r)
        assert "filter_reciter_name" not in props
        assert "filter_reciter_names" not in props
        mock_resolve.assert_not_called()

    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_dispatch_pushes_to_correct_buffer_key(self, mock_get_redis):
        """Event must land on TRACKING_BUFFER_KEY so flush task finds it."""
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage()
        def view(request):
            return {"results": [], "count": 0}

        view(self.factory.get("/recitations/"))

        assert mock_r.rpush.call_args[0][0] == TRACKING_BUFFER_KEY

    @patch("apps.usage_tracking.decorators.track_usage._get_tracking_redis")
    def test_dispatch_payload_is_valid_json_with_required_keys(self, mock_get_redis):
        """Flush task expects distinct_id, event, properties, meta keys."""
        mock_r = MagicMock()
        mock_get_redis.return_value = mock_r

        @track_usage()
        def view(request):
            return {"results": [], "count": 0}

        view(self.factory.get("/recitations/"))

        raw = mock_r.rpush.call_args[0][1]
        payload = json.loads(raw)
        assert "distinct_id" in payload
        assert "event" in payload
        assert "properties" in payload
        assert "meta" in payload


class TestDistinctId:
    def setup_method(self):
        self.factory = RequestFactory()

    def test_oauth_application(self):
        request = self.factory.get("/recitations/")
        request.access_token = SimpleNamespace(application=SimpleNamespace(id=5))
        assert _distinct_id(request) == "app-5"

    def test_jwt_authenticated_uses_user_pk(self):
        request = self.factory.get("/recitations/")
        request.user = SimpleNamespace(pk=99, is_authenticated=True)
        assert _distinct_id(request) == "user-99"

    def test_anonymous_falls_back_to_uuid(self):
        request = self.factory.get("/recitations/")
        request.user = AnonymousUser()
        result = _distinct_id(request)
        assert result.startswith("anon-")
        assert len(result) == 17  # "anon-" + 12 hex chars


class TestDetectAuthMethod:
    def setup_method(self):
        self.factory = RequestFactory()

    def test_oauth2_when_access_token(self):
        request = self.factory.get("/")
        request.access_token = SimpleNamespace(application=SimpleNamespace(id=1))
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

    def test_extracts_filters_as_int(self):
        result = _parse_query_params("reciter_id=6&riwayah_id=2")
        assert result == {"filter_reciter_id": 6, "filter_riwayah_id": 2}

    def test_invalid_page_skipped(self):
        assert _parse_query_params("page=abc") == {}


class TestResolveApplication:
    def test_no_token_returns_none_pair(self):
        assert _resolve_application(SimpleNamespace()) == (None, None)

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
