from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import Asset, Qiraah, Reciter, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.personalization.models import ListeningHistory
from apps.publishers.models import Publisher
from apps.users.models import User


def _make_recitation_asset(name="Test Asset"):
    """Helper to create a valid recitation Asset with all required FK fields."""
    publisher = baker.make(Publisher)
    resource = baker.make(Resource, publisher=publisher, category="recitation", status="ready")
    reciter = baker.make(Reciter, name=f"{name} Reciter", is_active=True)
    qiraah = baker.make(Qiraah, name=f"{name} Qiraah", is_active=True)
    riwayah = baker.make(Riwayah, qiraah=qiraah, name=f"{name} Riwayah", is_active=True)
    asset = baker.make(
        Asset,
        resource=resource,
        name=name,
        category="recitation",
        reciter=reciter,
        qiraah=qiraah,
        riwayah=riwayah,
    )
    return asset, reciter


class HistoryRecordTest(BaseTestCase):
    """Tests for POST /history/ endpoint."""

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="hist-user@example.com", is_active=True)
        self.app = Application.objects.create(
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App",
        )
        self.authenticate_client(self.app, self.user)
        self.asset, self.reciter = _make_recitation_asset("History Asset")

    def test_record_playback_should_return_201(self):
        # Act
        response = self.client.post(
            "/history/",
            data={"asset_id": self.asset.id, "position_ms": 60000, "duration_ms": 60000},
            format="json",
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual(self.asset.id, body["asset_id"])
        self.assertEqual("History Asset", body["asset_name"])
        self.assertEqual(60000, body["last_position_ms"])
        self.assertEqual(60000, body["duration_listened_ms"])
        self.assertIsNotNone(body["played_at"])

    def test_record_playback_with_reciter_should_include_reciter_info(self):
        # Act
        response = self.client.post(
            "/history/",
            data={"asset_id": self.asset.id, "position_ms": 30000},
            format="json",
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertIsNotNone(body["reciter"])
        self.assertEqual("History Asset Reciter", body["reciter"]["name"])

    def test_record_playback_upsert_should_update_existing(self):
        # Arrange — first record
        self.client.post(
            "/history/",
            data={"asset_id": self.asset.id, "position_ms": 30000, "duration_ms": 30000},
            format="json",
        )
        self.assertEqual(1, ListeningHistory.objects.filter(user=self.user).count())

        # Act — record again for same asset (upsert)
        response = self.client.post(
            "/history/",
            data={"asset_id": self.asset.id, "position_ms": 90000, "duration_ms": 60000},
            format="json",
        )

        # Assert — should update, not create new
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual(1, ListeningHistory.objects.filter(user=self.user).count())

        body = response.json()
        self.assertEqual(90000, body["last_position_ms"])
        self.assertEqual(60000, body["duration_listened_ms"])

    def test_record_playback_different_surah_should_create_separate_entry(self):
        # Arrange — surah 1
        self.client.post(
            "/history/",
            data={"asset_id": self.asset.id, "position_ms": 10000, "surah_number": 1},
            format="json",
        )

        # Act — surah 2
        self.client.post(
            "/history/",
            data={"asset_id": self.asset.id, "position_ms": 20000, "surah_number": 2},
            format="json",
        )

        # Assert — should have 2 entries
        self.assertEqual(2, ListeningHistory.objects.filter(user=self.user).count())

    def test_record_playback_with_nonexistent_asset_should_return_404(self):
        # Act
        response = self.client.post(
            "/history/",
            data={"asset_id": 99999, "position_ms": 1000},
            format="json",
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)


class HistoryListTest(BaseTestCase):
    """Tests for GET /history/ endpoint."""

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="hist-list@example.com", is_active=True)
        self.app = Application.objects.create(
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App",
        )
        self.authenticate_client(self.app, self.user)

    def test_get_history_empty_should_return_200(self):
        # Act
        response = self.client.get("/history/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(0, response.json()["count"])

    def test_get_history_should_return_recent_first(self):
        # Arrange
        asset1, _ = _make_recitation_asset("First Asset")
        asset2, _ = _make_recitation_asset("Second Asset")

        self.client.post(
            "/history/",
            data={"asset_id": asset1.id, "position_ms": 1000},
            format="json",
        )
        self.client.post(
            "/history/",
            data={"asset_id": asset2.id, "position_ms": 2000},
            format="json",
        )

        # Act
        response = self.client.get("/history/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        results = response.json()["results"]
        self.assertEqual(2, len(results))
        # Most recently played should be first
        self.assertEqual("Second Asset", results[0]["asset_name"])


class HistoryClearTest(BaseTestCase):
    """Tests for DELETE /history/ endpoint."""

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="hist-clear@example.com", is_active=True)
        self.app = Application.objects.create(
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            name="Test App",
        )
        self.authenticate_client(self.app, self.user)

    def test_clear_history_should_return_200(self):
        # Arrange
        asset, _ = _make_recitation_asset("Clear Asset")

        self.client.post(
            "/history/",
            data={"asset_id": asset.id, "position_ms": 1000},
            format="json",
        )

        # Act
        response = self.client.delete("/history/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(0, ListeningHistory.objects.filter(user=self.user).count())

    def test_clear_empty_history_should_return_200(self):
        # Act
        response = self.client.delete("/history/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn("0", response.json()["message"])
