from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, Qiraah, RecitationSurahTrack, Reciter, Riwayah, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationTracksListAPITest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.staff_user = User.objects.create_user(
            email="staff-list@example.com",
            name="Staff User",
            is_staff=True,
        )
        self.non_staff_user = User.objects.create_user(
            email="user-list@example.com",
            name="Regular User",
            is_staff=False,
            is_superuser=False,
        )

        self.publisher = baker.make(Publisher, name="List Publisher")
        self.reciter = baker.make(Reciter, name="List Reciter")
        self.qiraah = baker.make(Qiraah, name="List Qiraah")
        self.riwayah = baker.make(Riwayah, name="List Riwayah", qiraah=self.qiraah)

        self.recitation_asset = baker.make(
            Asset,
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="List Recitation",
        )
        self.other_asset = baker.make(
            Asset,
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Other List Recitation",
        )

        self.track_one = baker.make(
            RecitationSurahTrack,
            asset=self.recitation_asset,
            surah_number=1,
            audio_file=f"uploads/assets/{self.recitation_asset.id}/recitations/001.mp3",
            duration_ms=30000,
            size_bytes=1024,
        )
        self.track_two = baker.make(
            RecitationSurahTrack,
            asset=self.recitation_asset,
            surah_number=2,
            audio_file=f"uploads/assets/{self.recitation_asset.id}/recitations/002.mp3",
            duration_ms=45000,
            size_bytes=2048,
        )
        self.other_track = baker.make(
            RecitationSurahTrack,
            asset=self.other_asset,
            surah_number=3,
            audio_file=f"uploads/assets/{self.other_asset.id}/recitations/003.mp3",
        )

    def test_list_tracks_where_valid_asset_should_return_tracks_ordered_by_surah(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.READ_PORTAL_RECITATION)

        # Act
        response = self.client.get(
            f"/portal/recitations/{self.recitation_asset.slug}/recitation-tracks/",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertEqual(2, data["count"])
        results = data["results"]
        self.assertEqual(1, results[0]["surah_number"])
        self.assertEqual(2, results[1]["surah_number"])

    def test_list_tracks_where_valid_asset_should_return_correct_fields(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.READ_PORTAL_RECITATION)

        # Act
        response = self.client.get(
            f"/portal/recitations/{self.recitation_asset.slug}/recitation-tracks/",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        track = response.json()["results"][0]
        self.assertEqual(self.track_one.id, track["id"])
        self.assertEqual(1, track["surah_number"])
        self.assertEqual(30000, track["duration_ms"])
        self.assertEqual(1024, track["size_bytes"])
        self.assertIn("audio_url", track)
        self.assertIn("filename", track)

    def test_list_tracks_where_asset_belongs_to_different_asset_should_not_appear(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.READ_PORTAL_RECITATION)

        # Act
        response = self.client.get(
            f"/portal/recitations/{self.recitation_asset.slug}/recitation-tracks/",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        ids = [t["id"] for t in response.json()["results"]]
        self.assertNotIn(self.other_track.id, ids)

    def test_list_tracks_where_asset_not_found_should_return_404(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.READ_PORTAL_RECITATION)

        # Act
        response = self.client.get(
            "/portal/recitations/999999/recitation-tracks/",
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_list_tracks_where_asset_has_no_tracks_should_return_empty_list(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.READ_PORTAL_RECITATION)

        empty_asset = baker.make(
            Asset,
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            name="Empty Recitation",
        )

        # Act
        response = self.client.get(
            f"/portal/recitations/{empty_asset.slug}/recitation-tracks/",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(0, response.json()["count"])
        self.assertEqual([], response.json()["results"])

    def test_list_tracks_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.non_staff_user)

        # Act
        response = self.client.get(
            f"/portal/recitations/{self.recitation_asset.slug}/recitation-tracks/",
        )

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_list_tracks_where_unauthenticated_should_return_401(self):
        # Act
        response = self.client.get(
            f"/portal/recitations/{self.recitation_asset.slug}/recitation-tracks/",
        )

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_error", response.json()["error_name"])


class RecitationTracksDeleteAPITest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.staff_user = User.objects.create_user(
            email="staff-delete@example.com",
            name="Staff User",
            is_staff=True,
        )
        self.non_staff_user = User.objects.create_user(
            email="user-delete@example.com",
            name="Regular User",
            is_staff=False,
        )

        self.publisher = baker.make(Publisher, name="Delete Publisher")
        self.reciter = baker.make(Reciter, name="Delete Reciter")
        self.qiraah = baker.make(Qiraah, name="Delete Qiraah")
        self.riwayah = baker.make(Riwayah, name="Delete Riwayah", qiraah=self.qiraah)

        self.recitation_asset = baker.make(
            Asset,
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Delete Recitation",
        )
        self.other_asset = baker.make(
            Asset,
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Other Recitation",
        )

        self.track_one = baker.make(
            RecitationSurahTrack,
            asset=self.recitation_asset,
            surah_number=1,
            audio_file=f"uploads/assets/{self.recitation_asset.slug}/recitations/001.mp3",
        )
        self.track_two = baker.make(
            RecitationSurahTrack,
            asset=self.recitation_asset,
            surah_number=2,
            audio_file=f"uploads/assets/{self.recitation_asset.slug}/recitations/002.mp3",
        )
        self.other_track = baker.make(
            RecitationSurahTrack,
            asset=self.other_asset,
            surah_number=3,
            audio_file=f"uploads/assets/{self.other_asset.id}/recitations/003.mp3",
        )

    def test_delete_tracks_where_valid_payload_should_delete_tracks(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.DELETE_PORTAL_RECITATION)

        # Act
        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": [self.track_one.id, self.track_two.id]},
            format="json",
        )

        # Assert
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(RecitationSurahTrack.objects.filter(id=self.track_one.id).exists())
        self.assertFalse(RecitationSurahTrack.objects.filter(id=self.track_two.id).exists())

    def test_delete_tracks_where_track_ids_empty_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.DELETE_PORTAL_RECITATION)

        # Act
        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": []},
            format="json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("track_not_found", response.json()["error_name"])

    def test_delete_tracks_where_some_track_ids_do_not_exist_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.DELETE_PORTAL_RECITATION)

        # Act
        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": [self.track_one.id, 999999]},
            format="json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("track_not_found", response.json()["error_name"])

    def test_delete_tracks_where_all_track_ids_do_not_exist_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.DELETE_PORTAL_RECITATION)

        # Act
        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": [999998, 999999]},
            format="json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("track_not_found", response.json()["error_name"])

    def test_delete_tracks_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.non_staff_user)

        # Act
        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": [self.track_one.id]},
            format="json",
        )

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_delete_tracks_where_unauthenticated_should_return_401(self):
        # Act
        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": [self.track_one.id]},
            format="json",
        )

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_error", response.json()["error_name"])
