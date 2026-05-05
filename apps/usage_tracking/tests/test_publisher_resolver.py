from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser

from apps.usage_tracking.services.publisher_resolver import resolve_publisher_from_request


class TestPublisherResolver:
    def test_resolve_no_access_token_attr_returns_none(self):
        request = SimpleNamespace(user=AnonymousUser())

        publisher_id, slug, name = resolve_publisher_from_request(request)

        assert publisher_id is None
        assert slug is None

    def test_resolve_none_token_returns_none(self):
        request = SimpleNamespace(access_token=None, user=AnonymousUser())

        publisher_id, slug, name = resolve_publisher_from_request(request)

        assert publisher_id is None
        assert slug is None

    def test_resolve_token_without_application_returns_none(self):
        token = SimpleNamespace(application=None)
        request = SimpleNamespace(access_token=token, user=AnonymousUser())

        publisher_id, slug, name = resolve_publisher_from_request(request)

        assert publisher_id is None
        assert slug is None

    def test_resolve_application_without_owner_returns_none(self):
        token = SimpleNamespace(application=SimpleNamespace(user=None))
        request = SimpleNamespace(access_token=token, user=AnonymousUser())

        publisher_id, slug, name = resolve_publisher_from_request(request)

        assert publisher_id is None
        assert slug is None

    @patch("apps.usage_tracking.services.publisher_resolver._lookup_publisher_for_user")
    def test_resolve_app_owner_has_no_publisher_returns_none(self, mock_lookup):
        mock_lookup.return_value = (None, None, None)
        owner = MagicMock(name="owner")
        token = SimpleNamespace(application=SimpleNamespace(user=owner))
        request = SimpleNamespace(access_token=token, user=owner)

        publisher_id, slug, name = resolve_publisher_from_request(request)

        assert publisher_id is None
        assert slug is None
        mock_lookup.assert_called_once_with(owner)

    @patch("apps.usage_tracking.services.publisher_resolver._lookup_publisher_for_user")
    def test_resolve_valid_token_returns_publisher(self, mock_lookup):
        mock_lookup.return_value = (42, "acme-publisher", "Acme Publisher")
        owner = MagicMock(name="owner")
        token = SimpleNamespace(application=SimpleNamespace(user=owner))
        request = SimpleNamespace(access_token=token, user=owner)

        publisher_id, slug, name = resolve_publisher_from_request(request)

        assert publisher_id == 42
        assert slug == "acme-publisher"

    @patch("apps.usage_tracking.services.publisher_resolver._lookup_publisher_for_user")
    def test_resolve_caches_per_request(self, mock_lookup):
        mock_lookup.return_value = (42, "acme", "Acme")
        owner = MagicMock(name="owner")
        token = SimpleNamespace(application=SimpleNamespace(user=owner))
        request = SimpleNamespace(access_token=token, user=owner)

        resolve_publisher_from_request(request)
        resolve_publisher_from_request(request)

        assert mock_lookup.call_count == 1

    @patch("apps.usage_tracking.services.publisher_resolver.cache")
    @patch("apps.usage_tracking.services.publisher_resolver._lookup_publisher_for_user")
    def test_redis_stores_and_returns_tuple(self, mock_lookup, mock_cache):
        mock_lookup.return_value = (42, "acme", "Acme Publisher")
        mock_cache.get.return_value = None
        owner = MagicMock(name="owner")
        token = SimpleNamespace(pk=7, application=SimpleNamespace(user=owner))
        request = SimpleNamespace(access_token=token, user=owner)

        result = resolve_publisher_from_request(request)

        stored = mock_cache.set.call_args[0][1]
        assert isinstance(stored, tuple)
        assert result == (42, "acme", "Acme Publisher")
