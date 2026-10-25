import pytest

from apps.usage_tracking.checks import check_usage_identity_key
from apps.usage_tracking.services.traffic_identity import end_user_id_for, install_id_for, listener_id_for


class TestIdentity:
    @pytest.fixture(autouse=True)
    def _keys(self, settings):
        settings.SECRET_KEY = "secret-a"
        settings.USAGE_IDENTITY_KEY = ""

    def test_listener_id_for_where_same_ip_and_agent_should_be_stable(self):
        # Act
        first = listener_id_for("203.0.113.7", "Dalvik/2.1.0", "ray-1")
        second = listener_id_for("203.0.113.7", "Dalvik/2.1.0", "ray-2")

        # Assert
        assert first == second
        assert len(first) == 64
        assert "203.0.113.7" not in first

    def test_listener_id_for_where_agent_differs_should_differ(self):
        # Act / Assert
        assert listener_id_for("203.0.113.7", "A", "r") != listener_id_for("203.0.113.7", "B", "r")

    def test_listener_id_for_where_ip_missing_should_use_ray_so_requests_never_merge(self):
        # Act / Assert
        assert listener_id_for("", "A", "ray-1") != listener_id_for("", "A", "ray-2")

    def test_listener_id_for_where_identity_key_set_should_ignore_secret_key(self, settings):
        # Arrange
        settings.USAGE_IDENTITY_KEY = "identity"
        before = listener_id_for("203.0.113.7", "A", "r")

        # Act
        settings.SECRET_KEY = "secret-b"

        # Assert
        assert listener_id_for("203.0.113.7", "A", "r") == before

    def test_end_user_id_for_where_no_external_id_should_be_empty(self):
        # Act / Assert
        assert end_user_id_for("quran-companion", "") == ""

    def test_end_user_id_for_where_same_user_in_two_apps_should_differ(self):
        # Act / Assert
        assert end_user_id_for("app-a", "u1") != end_user_id_for("app-b", "u1")

    def test_install_id_for_where_raw_given_should_hash_it(self):
        # Act
        result = install_id_for("0b1c-uuid")

        # Assert
        assert len(result) == 64
        assert install_id_for("") == ""


class TestIdentityCheck:
    def test_check_usage_identity_key_where_import_enabled_without_key_should_warn(self, settings):
        # Arrange
        settings.ENABLE_USAGE_LOGPUSH_IMPORT = True
        settings.USAGE_IDENTITY_KEY = ""

        # Act
        messages = check_usage_identity_key()

        # Assert
        assert [message.id for message in messages] == ["usage_tracking.W001"]

    def test_check_usage_identity_key_where_key_set_should_pass(self, settings):
        # Arrange
        settings.ENABLE_USAGE_LOGPUSH_IMPORT = True
        settings.USAGE_IDENTITY_KEY = "identity"

        # Act / Assert
        assert check_usage_identity_key() == []
