from model_bakery import baker

from apps.content.models import Asset, Qiraah, RecitationSurahTrack, Reciter, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


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

        self.recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.recitation_asset = baker.make(
            Asset,
            resource=self.recitation_resource,
            category=Resource.CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Delete Recitation",
        )
        self.other_asset = baker.make(
            Asset,
            resource=self.recitation_resource,
            category=Resource.CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Other Recitation",
        )

        self.track_one = baker.make(
            RecitationSurahTrack,
            asset=self.recitation_asset,
            surah_number=1,
            audio_file=f"uploads/assets/{self.recitation_asset.id}/recitations/001.mp3",
        )
        self.track_two = baker.make(
            RecitationSurahTrack,
            asset=self.recitation_asset,
            surah_number=2,
            audio_file=f"uploads/assets/{self.recitation_asset.id}/recitations/002.mp3",
        )
        self.other_track = baker.make(
            RecitationSurahTrack,
            asset=self.other_asset,
            surah_number=3,
            audio_file=f"uploads/assets/{self.other_asset.id}/recitations/003.mp3",
        )

    def test_delete_tracks_where_valid_payload_should_delete_tracks(self):
        self.authenticate_user(self.staff_user)

        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": [self.track_one.id, self.track_two.id]},
            format="json",
        )

        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(RecitationSurahTrack.objects.filter(id=self.track_one.id).exists())
        self.assertFalse(RecitationSurahTrack.objects.filter(id=self.track_two.id).exists())

    def test_delete_tracks_where_track_ids_empty_should_return_400(self):
        self.authenticate_user(self.staff_user)

        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": []},
            format="json",
        )

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("track_not_found", response.json()["error_name"])

    def test_delete_tracks_where_some_track_ids_do_not_exist_should_return_400(self):
        self.authenticate_user(self.staff_user)

        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": [self.track_one.id, 999999]},
            format="json",
        )

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("track_not_found", response.json()["error_name"])

    def test_delete_tracks_where_all_track_ids_do_not_exist_should_return_400(self):
        self.authenticate_user(self.staff_user)

        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": [999998, 999999]},
            format="json",
        )

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("track_not_found", response.json()["error_name"])

    def test_delete_tracks_where_non_staff_should_return_403(self):
        self.authenticate_user(self.non_staff_user)

        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": [self.track_one.id]},
            format="json",
        )

        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_delete_tracks_where_unauthenticated_should_return_401(self):
        response = self.client.delete(
            "/portal/recitation-tracks/",
            {"track_ids": [self.track_one.id]},
            format="json",
        )

        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_error", response.json()["error_name"])
