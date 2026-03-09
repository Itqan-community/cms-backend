from model_bakery import baker
from oauth2_provider.models import Application

from apps.core.tests import BaseTestCase
from apps.personalization.models import UserPreference
from apps.users.models import User


class PreferenceGetTest(BaseTestCase):
    """Tests for GET /preferences/ endpoint."""

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="pref-user@example.com", is_active=True)
        self.app = Application.objects.create(
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App",
        )
        self.authenticate_client(self.app, self.user)

    def test_get_preferences_should_return_200_with_defaults(self):
        # Act
        response = self.client.get("/preferences/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual([], body["preferred_reciter_ids"])
        self.assertEqual([], body["preferred_qiraah_ids"])
        self.assertEqual([], body["preferred_riwayah_ids"])
        self.assertEqual("high", body["audio_quality"])
        self.assertEqual("en", body["language"])
        self.assertIn("new_content", body["notification_settings"])

    def test_get_preferences_should_create_preference_record(self):
        # Verify no preference exists before request
        self.assertFalse(UserPreference.objects.filter(user=self.user).exists())

        # Act
        response = self.client.get("/preferences/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(UserPreference.objects.filter(user=self.user).exists())

    def test_get_preferences_existing_should_return_saved_values(self):
        # Arrange — create preference with custom values
        UserPreference.objects.create(
            user=self.user,
            preferred_reciter_ids=[1, 2, 3],
            audio_quality="low",
            language="ar",
        )

        # Act
        response = self.client.get("/preferences/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual([1, 2, 3], body["preferred_reciter_ids"])
        self.assertEqual("low", body["audio_quality"])
        self.assertEqual("ar", body["language"])


class PreferenceUpdateTest(BaseTestCase):
    """Tests for PUT /preferences/ endpoint."""

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="pref-update@example.com", is_active=True)
        self.app = Application.objects.create(
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App",
        )
        self.authenticate_client(self.app, self.user)

    def test_update_preferences_should_return_200(self):
        # Act
        response = self.client.put(
            "/preferences/",
            data={
                "preferred_reciter_ids": [10, 20],
                "audio_quality": "medium",
                "language": "ar",
            },
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual([10, 20], body["preferred_reciter_ids"])
        self.assertEqual("medium", body["audio_quality"])
        self.assertEqual("ar", body["language"])

    def test_update_preferences_partial_should_only_change_provided_fields(self):
        # Arrange — first set some values
        self.client.put(
            "/preferences/",
            data={
                "preferred_reciter_ids": [1, 2, 3],
                "audio_quality": "high",
                "language": "en",
            },
            format="json",
        )

        # Act — update only language
        response = self.client.put(
            "/preferences/",
            data={"language": "ar"},
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual([1, 2, 3], body["preferred_reciter_ids"])  # Unchanged
        self.assertEqual("high", body["audio_quality"])  # Unchanged
        self.assertEqual("ar", body["language"])  # Changed

    def test_update_preferences_with_notification_settings(self):
        # Act
        response = self.client.put(
            "/preferences/",
            data={
                "notification_settings": {
                    "new_content": False,
                    "recommendations": True,
                },
            },
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertFalse(body["notification_settings"]["new_content"])
        self.assertTrue(body["notification_settings"]["recommendations"])

    def test_update_preferences_with_qiraah_and_riwayah_ids(self):
        # Act
        response = self.client.put(
            "/preferences/",
            data={
                "preferred_qiraah_ids": [5, 6],
                "preferred_riwayah_ids": [10, 11, 12],
            },
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual([5, 6], body["preferred_qiraah_ids"])
        self.assertEqual([10, 11, 12], body["preferred_riwayah_ids"])

    def test_update_preferences_with_invalid_audio_quality_should_return_422(self):
        # Act
        response = self.client.put(
            "/preferences/",
            data={"audio_quality": "ultra_hd"},
            format="json",
        )

        # Assert
        self.assertIn(response.status_code, [400, 422], response.content)
