import pytest

from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import UsageApp
from apps.usage_tracking.services.usage_apps import app_for_key, set_app_slug, slug_ids, unique_slug
from apps.users.models import APIKey, User


class TestUsageApps(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="dev@example.com", name="Dev")

    def _key(self, name: str) -> APIKey:
        api_key, _ = APIKey.objects.create_key(name=name, user=self.user)
        return api_key

    def test_api_key_where_created_should_get_usage_app_with_slug(self):
        # Act
        api_key = self._key("Quran Companion")

        # Assert
        app = UsageApp.objects.get(api_key=api_key)
        assert (app.slug, app.user_id, app.name) == ("quran-companion", self.user.id, "Quran Companion")

    def test_unique_slug_where_taken_or_not_latin_should_fall_back(self):
        # Arrange
        self._key("Quran Companion")

        # Act / Assert
        assert unique_slug("Quran Companion").startswith("quran-companion-")
        assert unique_slug("تطبيق").startswith("app")

    def test_api_key_where_deleted_should_keep_usage_app(self):
        # Arrange
        api_key = self._key("Temp")
        app_id = app_for_key(api_key).id

        # Act
        api_key.delete()

        # Assert
        assert UsageApp.objects.get(id=app_id).api_key_id is None

    def test_set_app_slug_where_invalid_or_taken_should_raise(self):
        # Arrange
        first, second = self._key("One"), self._key("Two")

        # Act / Assert
        with pytest.raises(ItqanError) as invalid:
            set_app_slug(first, "Bad Slug!")
        with pytest.raises(ItqanError) as taken:
            set_app_slug(first, app_for_key(second).slug)
        assert (invalid.value.error_name, taken.value.error_name) == ("invalid_app_slug", "app_slug_taken")

    def test_slug_ids_where_known_and_unknown_should_map_known_only(self):
        # Arrange
        app = app_for_key(self._key("Known"))

        # Act / Assert
        assert slug_ids(["known", "nope"]) == {"known": app.id}

    def test_slug_for_key_where_called_twice_should_hit_cache_and_follow_renames(self):
        # Arrange
        from apps.usage_tracking.services.usage_apps import slug_for_key

        api_key = self._key("Cached App")
        slug_for_key(api_key)

        # Act / Assert
        with self.assertNumQueries(0):
            assert slug_for_key(api_key) == "cached-app"
        with self.captureOnCommitCallbacks(execute=True):
            set_app_slug(api_key, "renamed-app")
        assert slug_for_key(api_key) == "renamed-app"

    def test_set_app_slug_where_not_committed_yet_should_keep_the_cached_slug(self):
        # Arrange
        from apps.usage_tracking.services.usage_apps import slug_for_key

        api_key = self._key("Pending App")
        slug_for_key(api_key)

        # Act
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            set_app_slug(api_key, "pending-new")
            cached_before_commit = slug_for_key(api_key)

        # Assert: a request during the transaction cannot re-cache a stale slug after it.
        assert cached_before_commit == "pending-app"
        assert len(callbacks) == 1

    def test_app_for_key_where_slug_is_taken_meanwhile_should_retry_with_a_new_slug(self):
        # Arrange
        from unittest.mock import patch

        from apps.usage_tracking.services import usage_apps

        api_key = self._key("Racer")
        UsageApp.objects.filter(api_key=api_key).delete()
        UsageApp.objects.create(name="Other", slug="racer")
        slugs = iter(["racer", "racer-2"])

        # Act
        with patch.object(usage_apps, "unique_slug", lambda name: next(slugs)):
            app = app_for_key(api_key)

        # Assert
        assert (app.slug, app.api_key_id) == ("racer-2", api_key.id)

    def test_unique_slug_where_name_has_underscores_should_use_hyphens(self):
        # Act / Assert
        assert unique_slug("my_app") == "my-app"
