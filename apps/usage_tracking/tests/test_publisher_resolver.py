from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache

from apps.usage_tracking.services.publisher_resolver import resolve_publisher_from_request


class TestPublisherResolver:
    def setup_method(self):
        cache.clear()
    def test_resolve_no_user_attr_returns_none(self):
        request = SimpleNamespace()

        publisher_id, slug = resolve_publisher_from_request(request)

        assert publisher_id is None
        assert slug is None

    def test_resolve_anonymous_user_returns_none(self):
        request = SimpleNamespace(user=AnonymousUser())

        publisher_id, slug = resolve_publisher_from_request(request)

        assert publisher_id is None
        assert slug is None

    @patch("apps.usage_tracking.services.publisher_resolver.cache")
    @patch("apps.usage_tracking.services.publisher_resolver._lookup_publisher_for_user")
    def test_resolve_authenticated_user_with_no_publisher_returns_none(self, mock_lookup, mock_cache):
        mock_cache.get.return_value = None
        mock_lookup.return_value = (None, None)
        user = SimpleNamespace(is_authenticated=True, pk=1)
        request = SimpleNamespace(user=user)

        publisher_id, slug = resolve_publisher_from_request(request)

        assert publisher_id is None
        assert slug is None
        mock_lookup.assert_called_once_with(user)

    @patch("apps.usage_tracking.services.publisher_resolver.cache")
    @patch("apps.usage_tracking.services.publisher_resolver._lookup_publisher_for_user")
    def test_resolve_authenticated_user_returns_publisher(self, mock_lookup, mock_cache):
        mock_cache.get.return_value = None
        mock_lookup.return_value = (42, "acme-publisher")
        user = SimpleNamespace(is_authenticated=True, pk=2)
        request = SimpleNamespace(user=user)

        publisher_id, slug = resolve_publisher_from_request(request)

        assert publisher_id == 42
        assert slug == "acme-publisher"

    @patch("apps.usage_tracking.services.publisher_resolver.cache")
    @patch("apps.usage_tracking.services.publisher_resolver._lookup_publisher_for_user")
    def test_resolve_caches_per_request(self, mock_lookup, mock_cache):
        mock_cache.get.return_value = None
        mock_lookup.return_value = (42, "acme")
        user = SimpleNamespace(is_authenticated=True, pk=3)
        request = SimpleNamespace(user=user)

        resolve_publisher_from_request(request)
        resolve_publisher_from_request(request)

        assert mock_lookup.call_count == 1
