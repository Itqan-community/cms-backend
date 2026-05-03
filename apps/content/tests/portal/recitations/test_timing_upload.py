import json

from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetVersion,
    CategoryChoice,
    Qiraah,
    RecitationAyahTiming,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
    StatusChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User

URL = "/portal/timing/upload/"


def make_timing_file(surah_number: int, ayahs: list[dict] | None = None) -> SimpleUploadedFile:
    """Build a valid timing JSON file for the given surah."""
    if ayahs is None:
        ayahs = [
            {"ayah_number": 1, "start": 0.0, "end": 5.0},
            {"ayah_number": 2, "start": 5.0, "end": 10.0},
        ]
    payload = json.dumps({"surah_id": surah_number, "ayahs": ayahs}).encode("utf-8")
    return SimpleUploadedFile(
        name=f"{surah_number:03d}.json",
        content=payload,
        content_type="application/json",
    )


class TimingUploadBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            name="Staff User",
            is_staff=True,
        )
        self.non_staff_user = User.objects.create_user(
            email="user@example.com",
            name="Regular User",
            is_staff=False,
        )

        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.reciter = baker.make(Reciter, name="Test Reciter", slug="test-reciter")
        self.qiraah = baker.make(Qiraah, name="Test Qiraah")
        self.riwayah = baker.make(Riwayah, name="Test Riwayah", qiraah=self.qiraah)

        self.asset = baker.make(
            Asset,
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            reciter=self.reciter,
            qiraah=self.qiraah,
            riwayah=self.riwayah,
            name="Test Recitation",
        )

        # Track for surah 1 so the service can match uploaded files
        self.track = baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
        )

        # AssetVersion required by sync_asset_recitations_json_file
        self.asset_version = baker.make(
            AssetVersion,
            asset=self.asset,
            name="v1",
        )


class TimingUploadSuccessTest(TimingUploadBaseTest):
    def test_upload_timing_where_valid_files_should_return_200(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.UPLOAD_PORTAL_TIMING)
        timing_file = make_timing_file(surah_number=1)

        # Act
        response = self.client.post(
            URL,
            data={
                "asset_id": self.asset.id,
                "files": [timing_file],
            },
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(self.asset.id, body["asset_id"])
        self.assertEqual(2, body["created_total"])
        self.assertEqual(0, body["updated_total"])
        self.assertEqual(0, body["skipped_total"])
        self.assertEqual([], body["missing_tracks"])
        self.assertEqual([], body["file_errors"])
        self.assertIsNotNone(body["synced_file_url"])
        self.assertIsNotNone(body["synced_filename"])
        self.assertIn("recitations.json", body["synced_filename"])

        # Verify ayah timings were actually persisted
        self.assertEqual(2, RecitationAyahTiming.objects.filter(track=self.track).count())

    def test_upload_timing_where_existing_timings_should_update_and_skip(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.UPLOAD_PORTAL_TIMING)
        # Pre-create one timing (will be updated) and one that won't change (will be skipped)
        baker.make(
            RecitationAyahTiming,
            track=self.track,
            ayah_key="1:1",
            start_ms=0,
            end_ms=4000,  # differs from file (5000ms) -> will be updated
            duration_ms=4000,
        )
        baker.make(
            RecitationAyahTiming,
            track=self.track,
            ayah_key="1:2",
            start_ms=5000,
            end_ms=10000,  # same as file -> will be skipped
            duration_ms=5000,
        )
        timing_file = make_timing_file(surah_number=1)

        # Act
        response = self.client.post(
            URL,
            data={
                "asset_id": self.asset.id,
                "files": [timing_file],
            },
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(0, body["created_total"])
        self.assertEqual(1, body["updated_total"])
        self.assertEqual(1, body["skipped_total"])

    def test_upload_timing_where_missing_track_for_surah_should_report_in_missing_tracks(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.UPLOAD_PORTAL_TIMING)
        # File for surah 2, but no track exists for surah 2
        timing_file = make_timing_file(surah_number=2)

        # Act
        response = self.client.post(
            URL,
            data={
                "asset_id": self.asset.id,
                "files": [timing_file],
            },
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(0, body["created_total"])
        self.assertIn(2, body["missing_tracks"])

    def test_upload_timing_where_no_asset_version_should_create_asset_version(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.UPLOAD_PORTAL_TIMING)
        # Delete the AssetVersion so sync will create a new one
        self.asset_version.delete()
        timing_file = make_timing_file(surah_number=1)

        # Act
        response = self.client.post(
            URL,
            data={
                "asset_id": self.asset.id,
                "files": [timing_file],
            },
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIsNotNone(AssetVersion.objects.filter(asset_id=self.asset.id, name="1").first())

        # Verify the timing upload was also added
        self.assertEqual(2, RecitationAyahTiming.objects.filter(track=self.track).count())


class TimingUploadAuthTest(TimingUploadBaseTest):
    def test_upload_timing_where_unauthenticated_should_return_401(self):
        # Arrange
        timing_file = make_timing_file(surah_number=1)

        # Act
        response = self.client.post(
            URL,
            data={
                "asset_id": self.asset.id,
                "files": [timing_file],
            },
        )

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_upload_timing_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.non_staff_user)
        timing_file = make_timing_file(surah_number=1)

        # Act
        response = self.client.post(
            URL,
            data={
                "asset_id": self.asset.id,
                "files": [timing_file],
            },
        )

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])


class TimingUploadErrorTest(TimingUploadBaseTest):
    def test_upload_timing_where_asset_not_found_should_return_404(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.UPLOAD_PORTAL_TIMING)
        timing_file = make_timing_file(surah_number=1)

        # Act
        response = self.client.post(
            URL,
            data={
                "asset_id": 99999,
                "files": [timing_file],
            },
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])

    def test_upload_timing_where_malformed_json_file_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.UPLOAD_PORTAL_TIMING)
        bad_file = SimpleUploadedFile(
            name="001.json",
            content=b"not valid json {{{{",
            content_type="application/json",
        )

        # Act
        response = self.client.post(
            URL,
            data={
                "asset_id": self.asset.id,
                "files": [bad_file],
            },
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("upload_failed", response.json()["error_name"])

    def test_upload_timing_where_end_before_start_should_return_400(self):
        # Arrange
        self.authenticate_user(self.staff_user)
        self.give_permission(self.staff_user, PermissionChoice.UPLOAD_PORTAL_TIMING)
        timing_file = make_timing_file(
            surah_number=1,
            ayahs=[{"ayah_number": 1, "start": 10.0, "end": 5.0}],  # end < start
        )

        # Act
        response = self.client.post(
            URL,
            data={
                "asset_id": self.asset.id,
                "files": [timing_file],
            },
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("upload_failed", response.json()["error_name"])
