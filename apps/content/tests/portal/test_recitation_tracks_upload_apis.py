from unittest.mock import patch

from model_bakery import baker

from apps.content.models import Asset, Qiraah, RecitationSurahTrack, Reciter, Resource, Riwayah
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationTracksUploadAPITest(BaseTestCase):
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

        self.publisher = baker.make(Publisher, name="Portal Publisher")
        self.reciter = baker.make(Reciter, name="Portal Reciter")
        self.qiraah = baker.make(Qiraah, name="Portal Qiraah")
        self.riwayah = baker.make(Riwayah, name="Portal Riwayah", qiraah=self.qiraah)

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
            name="Portal Recitation",
        )

        self.non_recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.MUSHAF,
            status=Resource.StatusChoice.READY,
        )
        self.non_recitation_asset = baker.make(
            Asset,
            resource=self.non_recitation_resource,
            category=Resource.CategoryChoice.MUSHAF,
            reciter=None,
            qiraah=None,
            riwayah=None,
            name="Portal Mushaf",
        )

        self.existing_track = baker.make(
            RecitationSurahTrack,
            asset=self.recitation_asset,
            surah_number=1,
            audio_file=f"uploads/assets/{self.recitation_asset.id}/recitations/001.mp3",
            original_filename="001.mp3",
        )

    def test_validate_upload_where_all_files_are_new_should_return_valid(self):
        self.authenticate_user(self.staff_user)

        response = self.client.post(
            "/portal/recitation-tracks/validate-upload/",
            {"asset_id": self.recitation_asset.id, "filenames": ["002.mp3", "003.mp3"]},
            format="json",
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("valid", body["status"])
        self.assertEqual("All files are valid and ready to upload.", body["message"])
        self.assertEqual(
            [
                {"filename": "002.mp3", "status": "valid"},
                {"filename": "003.mp3", "status": "valid"},
            ],
            body["files"],
        )

    def test_validate_upload_where_mix_of_new_existing_and_invalid_should_return_invalid(self):
        self.authenticate_user(self.staff_user)

        response = self.client.post(
            "/portal/recitation-tracks/validate-upload/",
            {
                "asset_id": self.recitation_asset.id,
                "filenames": ["002.mp3", "001.mp3", "bad.mp3", "002.mp3"],
            },
            format="json",
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("invalid", body["status"])
        self.assertEqual(
            "Some files are invalid (either for naming or extension or duplication). Fix them and try again.",
            body["message"],
        )
        self.assertEqual(
            [
                {"filename": "002.mp3", "status": "valid"},
                {"filename": "001.mp3", "status": "skip"},
                {"filename": "bad.mp3", "status": "invalid"},
                {"filename": "002.mp3", "status": "invalid"},
            ],
            body["files"],
        )

    def test_validate_upload_where_filename_extension_is_not_mp3_should_return_invalid(self):
        self.authenticate_user(self.staff_user)

        response = self.client.post(
            "/portal/recitation-tracks/validate-upload/",
            {"asset_id": self.recitation_asset.id, "filenames": ["002.wav"]},
            format="json",
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("invalid", body["status"])
        self.assertEqual(
            "Some files are invalid (either for naming or extension or duplication). Fix them and try again.",
            body["message"],
        )
        self.assertEqual(
            [{"filename": "002.wav", "status": "invalid"}],
            body["files"],
        )

    def test_validate_upload_where_all_files_exist_should_return_invalid(self):
        self.authenticate_user(self.staff_user)

        response = self.client.post(
            "/portal/recitation-tracks/validate-upload/",
            {"asset_id": self.recitation_asset.id, "filenames": ["001.mp3"]},
            format="json",
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("invalid", body["status"])
        self.assertEqual(
            "All submitted files already have uploaded tracks. No new files to upload.",
            body["message"],
        )

    def test_validate_upload_where_empty_list_should_return_invalid(self):
        self.authenticate_user(self.staff_user)

        response = self.client.post(
            "/portal/recitation-tracks/validate-upload/",
            {"asset_id": self.recitation_asset.id, "filenames": []},
            format="json",
        )

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("invalid", body["status"])
        self.assertEqual([], body["files"])

    def test_validate_upload_where_asset_not_found_should_return_404(self):
        self.authenticate_user(self.staff_user)

        response = self.client.post(
            "/portal/recitation-tracks/validate-upload/",
            {"asset_id": 999999, "filenames": ["001.mp3"]},
            format="json",
        )

        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("not_found", response.json()["error_name"])

    def test_validate_upload_where_non_staff_should_return_403(self):
        self.authenticate_user(self.non_staff_user)

        response = self.client.post(
            "/portal/recitation-tracks/validate-upload/",
            {"asset_id": self.recitation_asset.id, "filenames": ["001.mp3"]},
            format="json",
        )

        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_start_upload_should_delegate_to_service(self):
        self.authenticate_user(self.staff_user)

        with patch(
            "apps.content.api.portal.recitation_tracks_bulk.AssetRecitationAudioTracksDirectUploadService.start_upload",
            return_value={
                "key": "uploads/assets/1/recitations/002.mp3",
                "uploadId": "upload-123",
                "contentType": "audio/mpeg",
                "surahNumber": 2,
            },
        ) as start_upload:
            response = self.client.post(
                "/portal/recitation-tracks/uploads/start/",
                {
                    "asset_id": self.recitation_asset.id,
                    "filename": "002.mp3",
                    "duration_ms": 1000,
                    "size_bytes": 1024,
                },
                format="json",
            )

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            {
                "key": "uploads/assets/1/recitations/002.mp3",
                "upload_id": "upload-123",
                "content_type": "audio/mpeg",
                "surah_number": 2,
            },
            response.json(),
        )
        start_upload.assert_called_once_with(asset_id=self.recitation_asset.id, filename="002.mp3")

    def test_start_upload_where_service_raises_should_propagate_itqan_error(self):
        self.authenticate_user(self.staff_user)

        with patch(
            "apps.content.api.portal.recitation_tracks_bulk.AssetRecitationAudioTracksDirectUploadService.start_upload",
            side_effect=ItqanError("duplicate_track", "Track already exists", status_code=409),
        ):
            response = self.client.post(
                "/portal/recitation-tracks/uploads/start/",
                {"asset_id": self.recitation_asset.id, "filename": "001.mp3"},
                format="json",
            )

        self.assertEqual(409, response.status_code, response.content)
        self.assertEqual("duplicate_track", response.json()["error_name"])

    def test_sign_part_should_return_presigned_url(self):
        self.authenticate_user(self.staff_user)

        with patch(
            "apps.content.api.portal.recitation_tracks_bulk.AssetRecitationAudioTracksDirectUploadService.sign_part",
            return_value={"url": "https://example.test/presigned"},
        ) as sign_part:
            response = self.client.post(
                "/portal/recitation-tracks/uploads/sign-part/",
                {"key": "uploads/assets/1/recitations/002.mp3", "upload_id": "upload-123", "part_number": 1},
                format="json",
            )

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({"url": "https://example.test/presigned"}, response.json())
        sign_part.assert_called_once_with(
            key="uploads/assets/1/recitations/002.mp3",
            upload_id="upload-123",
            part_number=1,
        )

    def test_finish_upload_should_delegate_to_service(self):
        self.authenticate_user(self.staff_user)

        with patch(
            "apps.content.api.portal.recitation_tracks_bulk.AssetRecitationAudioTracksDirectUploadService.finish_upload",
            return_value={
                "trackId": 55,
                "assetId": self.recitation_asset.id,
                "surahNumber": 2,
                "sizeBytes": 777,
                "finishedAt": "2026-04-08T12:00:00+03:00",
                "key": "uploads/assets/1/recitations/002.mp3",
            },
        ) as finish_upload:
            response = self.client.post(
                "/portal/recitation-tracks/uploads/finish/",
                {
                    "asset_id": self.recitation_asset.id,
                    "filename": "002.mp3",
                    "key": "uploads/assets/1/recitations/002.mp3",
                    "upload_id": "upload-123",
                    "parts": [{"ETag": '"etag-1"', "PartNumber": 1}],
                    "duration_ms": 2000,
                    "size_bytes": 777,
                },
                format="json",
            )

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(55, response.json()["track_id"])
        self.assertEqual(self.recitation_asset.id, response.json()["asset_id"])
        self.assertEqual(2, response.json()["surah_number"])
        self.assertEqual(777, response.json()["size_bytes"])
        finish_upload.assert_called_once_with(
            key="uploads/assets/1/recitations/002.mp3",
            upload_id="upload-123",
            parts=[{"ETag": '"etag-1"', "PartNumber": 1}],
            asset_id=self.recitation_asset.id,
            filename="002.mp3",
            duration_ms=2000,
            size_bytes=777,
        )

    def test_abort_upload_should_return_aborted_payload(self):
        self.authenticate_user(self.staff_user)

        with patch(
            "apps.content.api.portal.recitation_tracks_bulk.AssetRecitationAudioTracksDirectUploadService.abort_upload",
            return_value={"aborted": True},
        ) as abort_upload:
            response = self.client.post(
                "/portal/recitation-tracks/uploads/abort/",
                {"key": "uploads/assets/1/recitations/002.mp3", "upload_id": "upload-123"},
                format="json",
            )

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            {"key": "uploads/assets/1/recitations/002.mp3", "upload_id": "upload-123", "aborted": True},
            response.json(),
        )
        abort_upload.assert_called_once_with(
            key="uploads/assets/1/recitations/002.mp3",
            upload_id="upload-123",
        )

    def test_upload_endpoints_where_unauthenticated_should_return_401(self):
        response = self.client.post(
            "/portal/recitation-tracks/uploads/sign-part/",
            {"key": "uploads/assets/1/recitations/002.mp3", "upload_id": "upload-123", "part_number": 1},
            format="json",
        )

        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_error", response.json()["error_name"])

    def test_admin_uploads_start_view_should_still_work(self):
        self.client.force_login(self.staff_user)

        with patch(
            "apps.content.admin.AssetRecitationAudioTracksDirectUploadService.start_upload",
            return_value={
                "key": "uploads/assets/1/recitations/002.mp3",
                "uploadId": "legacy-upload-1",
                "contentType": "audio/mpeg",
                "surahNumber": 2,
                "assetId": self.recitation_asset.id,
                "filename": "002.mp3",
            },
        ) as start_upload:
            response = self.client.post(
                "/django-admin/content/asset/uploads/start/",
                data={"assetId": self.recitation_asset.id, "filename": "002.mp3"},
                format="json",
            )

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("legacy-upload-1", response.json()["uploadId"])
        start_upload.assert_called_once_with(asset_id=self.recitation_asset.id, filename="002.mp3")
