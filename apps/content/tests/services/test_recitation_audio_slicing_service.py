from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
from unittest.mock import Mock, patch

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    CategoryChoice,
    RecitationAyahTiming,
    RecitationFolder,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
)
from apps.content.services.admin.recitation_audio_slicing_service import RecitationAudioSlicingService
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase

SOURCE_BODY = b"fake-source-mp3-bytes"


class TestRecitationAudioSlicingService(BaseTestCase):
    def setUp(self) -> None:
        self.asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=baker.make(Reciter, name="Test Reciter", slug="test-reciter"),
            riwayah=baker.make(Riwayah, name="Test Riwayah"),
        )
        self.default_folder = RecitationFolder.objects.get(asset=self.asset, is_default=True)
        self.track = RecitationSurahTrack.objects.create(
            asset=self.asset,
            folder=self.default_folder,
            surah_number=1,
            audio_file=SimpleUploadedFile("001.mp3", b"x"),
            duration_ms=5000,
        )
        self.service = RecitationAudioSlicingService()
        # The service builds a client against the R2 endpoint (localhost:5000 under the
        # test override), which moto does not intercept. Point it at a moto-intercepted
        # client so the S3 calls stay real (in-memory) rather than mocked.
        self.s3 = boto3.client("s3", region_name="us-east-1")
        client_patcher = patch.object(self.service, "_get_s3_client", return_value=self.s3)
        client_patcher.start()
        self.addCleanup(client_patcher.stop)
        self._clear_bucket()

    def _add_timing(self, ayah_key: str, start_ms: int, end_ms: int, track=None) -> RecitationAyahTiming:
        return RecitationAyahTiming.objects.create(
            track=track or self.track, ayah_key=ayah_key, start_ms=start_ms, end_ms=end_ms
        )

    def _upload_source_audio(self, track=None) -> str:
        """Put the track's source MP3 in the bucket under the key the service reads from."""
        track = track or self.track
        key = f"media/{track.audio_file.name}"
        self.s3.put_object(Bucket=self.bucket_name, Key=key, Body=SOURCE_BODY)
        return key

    def _bucket_keys(self) -> list[str]:
        response = self.s3.list_objects_v2(Bucket=self.bucket_name)
        return [obj["Key"] for obj in response.get("Contents", [])]

    def _clear_bucket(self) -> None:
        """The moto bucket is class-scoped; drop objects from previous tests so key assertions stay isolated."""
        while True:
            keys = self._bucket_keys()
            if not keys:
                break
            self.s3.delete_objects(Bucket=self.bucket_name, Delete={"Objects": [{"Key": key} for key in keys]})

    def _fake_ffmpeg(self, output_body: bytes):
        """Stand-in for the ffmpeg binary: writes bytes to the output path and exits 0."""

        def fake_run(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(output_body)
            return subprocess.CompletedProcess(args=cmd, returncode=0)

        return fake_run

    def _assert_slicing_rejected(self, ctx, error_name: str, status_code: int) -> None:
        self.assertEqual(error_name, ctx.exception.error_name)
        self.assertEqual(status_code, ctx.exception.status_code)

    def _failing_storage_client(self, *, download_error=None, upload_error=None) -> Mock:
        """Mock S3 client whose download/upload can be made to fail with a given exception."""
        s3 = Mock()
        if download_error is not None:
            s3.get_object.side_effect = download_error
        else:
            s3.get_object.return_value = {"Body": Mock(read=Mock(side_effect=[b"source-bytes", b""]))}
        if upload_error is not None:
            s3.put_object.side_effect = upload_error
        return s3

    def test_slice_track_where_track_does_not_exist_should_raise_track_not_found(self):
        # Arrange / Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service.slice_track(track_id=999999)

        self._assert_slicing_rejected(ctx, "track_not_found", 404)

    def test_slice_track_where_track_has_no_timings_should_return_zero_sliced(self):
        # Arrange
        self._upload_source_audio()

        # Act
        result = self.service.slice_track(self.track.id)

        # Assert - no slicing attempted, no objects written
        self.assertEqual(self.track.id, result["track_id"])
        self.assertEqual(self.asset.id, result["asset_id"])
        self.assertEqual(0, result["sliced"])
        self.assertEqual([], result["keys"])
        self.assertEqual([f"media/{self.track.audio_file.name}"], self._bucket_keys())

    def test_slice_track_where_valid_timings_should_upload_one_object_per_ayah_with_deterministic_keys(self):
        # Arrange
        source_key = self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=1234)
        self._add_timing("1:2", start_ms=1234, end_ms=3456)

        # Act
        with patch("subprocess.run", side_effect=self._fake_ffmpeg(b"slice-bytes")):
            result = self.service.slice_track(self.track.id)

        expected_keys = [
            f"uploads/assets/{self.asset.id}/recitations/{self.default_folder.id}/001/ayah_001.mp3",
            f"uploads/assets/{self.asset.id}/recitations/{self.default_folder.id}/001/ayah_002.mp3",
        ]

        # Assert - deterministic keys, one object per ayah, mp3 content type
        self.assertEqual(2, result["sliced"])
        self.assertEqual(expected_keys, result["keys"])
        self.assertEqual([source_key] + [f"media/{key}" for key in expected_keys], sorted(self._bucket_keys()))

        s3 = self.s3
        head = s3.head_object(Bucket=self.bucket_name, Key=f"media/{expected_keys[0]}")
        self.assertEqual("audio/mpeg", head["ContentType"])
        body = s3.get_object(Bucket=self.bucket_name, Key=f"media/{expected_keys[0]}")["Body"].read()
        self.assertEqual(b"slice-bytes", body)

    def test_slice_track_where_timings_have_millisecond_precision_should_pass_ss_and_to_in_seconds(self):
        # Arrange
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=1234, end_ms=3456)

        # Act
        with patch("subprocess.run", side_effect=self._fake_ffmpeg(b"x")) as mock_run:
            self.service.slice_track(self.track.id)

        # Assert - ffmpeg receives seconds with ms precision, as output options (after -i)
        cmd = mock_run.call_args.args[0]
        self.assertEqual("-ss", cmd[cmd.index("-ss") + 0])
        self.assertEqual("1.234", cmd[cmd.index("-ss") + 1])
        self.assertEqual("3.456", cmd[cmd.index("-to") + 1])
        self.assertGreater(cmd.index("-ss"), cmd.index("-i"))

    def test_slice_track_where_ayah_is_sliced_should_apply_short_in_and_out_fades(self):
        # Arrange - 2.224s ayah => fade-out starts at 2.224 - 0.02 = 2.204
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=2224)

        # Act
        with patch("subprocess.run", side_effect=self._fake_ffmpeg(b"x")) as mock_run:
            self.service.slice_track(self.track.id)

        # Assert
        cmd = mock_run.call_args.args[0]
        fade = cmd[cmd.index("-af") + 1]
        self.assertEqual("afade=t=in:st=0:d=0.02,afade=t=out:st=2.204:d=0.02", fade)

    def test_slice_track_where_ayah_shorter_than_fade_should_clamp_fade_out_start(self):
        # Arrange - a 10ms ayah is shorter than the 20ms fade; the fade-out start must never be negative
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=10)

        # Act
        with patch("subprocess.run", side_effect=self._fake_ffmpeg(b"x")) as mock_run:
            self.service.slice_track(self.track.id)

        # Assert
        cmd = mock_run.call_args.args[0]
        fade = cmd[cmd.index("-af") + 1]
        self.assertEqual("afade=t=in:st=0:d=0.02,afade=t=out:st=0.020:d=0.02", fade)

    def test_build_slice_key_where_two_folders_should_produce_distinct_storage_keys(self):
        # Arrange
        echo_folder = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")

        # Act
        default_key = self.service._build_slice_key(self.asset.id, self.default_folder.id, 1, 1)
        echo_key = self.service._build_slice_key(self.asset.id, echo_folder.id, 1, 1)

        # Assert - the folder segment stops variants from overwriting each other
        self.assertNotEqual(default_key, echo_key)
        self.assertEqual(
            f"uploads/assets/{self.asset.id}/recitations/{self.default_folder.id}/001/ayah_001.mp3", default_key
        )
        self.assertEqual(f"uploads/assets/{self.asset.id}/recitations/{echo_folder.id}/001/ayah_001.mp3", echo_key)

    def test_slice_track_where_same_surah_exists_in_two_folders_should_write_distinct_objects(self):
        # Arrange
        echo_folder = RecitationFolder.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        echo_track = RecitationSurahTrack.objects.create(
            asset=self.asset,
            folder=echo_folder,
            surah_number=1,
            audio_file=SimpleUploadedFile("001-echo.mp3", b"x"),
            duration_ms=5000,
        )
        self._upload_source_audio(self.track)
        self._upload_source_audio(echo_track)
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        self._add_timing("1:1", start_ms=100, end_ms=1100, track=echo_track)

        # Act
        with patch("subprocess.run", side_effect=self._fake_ffmpeg(b"x")):
            default_result = self.service.slice_track(self.track.id)
            echo_result = self.service.slice_track(echo_track.id)

        # Assert - two separate ayah objects, none overwritten
        self.assertNotEqual(default_result["keys"], echo_result["keys"])
        slice_keys = [key for key in self._bucket_keys() if "/ayah_" in key]
        self.assertEqual(2, len(slice_keys))

    def test_slice_track_where_end_ms_exceeds_track_duration_should_fail_whole_track_with_no_objects(self):
        # Arrange - one valid + one invalid timing: nothing may be written for the valid one
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        self._add_timing("1:2", start_ms=0, end_ms=6000)  # track duration_ms = 5000

        # Act / Assert
        with patch("subprocess.run") as mock_run:
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "invalid_ayah_timing", 400)
        self.assertIn("must not exceed the track duration", ctx.exception.message)
        mock_run.assert_not_called()
        self.assertEqual([f"media/{self.track.audio_file.name}"], self._bucket_keys())

    def test_slice_track_where_end_ms_equals_start_ms_should_fail_whole_track(self):
        # Arrange
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=1000, end_ms=1000)

        # Act / Assert
        with patch("subprocess.run") as mock_run:
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "invalid_ayah_timing", 400)
        self.assertIn("greater than start_ms", ctx.exception.message)
        mock_run.assert_not_called()

    def test_slice_track_where_end_ms_before_start_ms_should_fail_whole_track(self):
        # Arrange
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=2000, end_ms=1000)

        # Act / Assert
        with patch("subprocess.run") as mock_run:
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "invalid_ayah_timing", 400)
        self.assertIn("greater than start_ms", ctx.exception.message)
        mock_run.assert_not_called()

    def test_validate_timings_where_start_ms_negative_should_fail_whole_track(self):
        # Arrange - PositiveIntegerField rejects negative values at the DB level, so exercise
        # the service guard directly against a timing-like object
        negative_timing = Mock(start_ms=-1, end_ms=100, ayah_key="1:1")

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            self.service._validate_timings(self.track, [negative_timing])

        self._assert_slicing_rejected(ctx, "invalid_ayah_timing", 400)
        self.assertIn("must not be negative", ctx.exception.message)

    def test_slice_track_where_ayah_key_mismatches_track_surah_should_fail_whole_track(self):
        # Arrange - a valid timing plus one from another surah: the whole track must be rejected
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        self._add_timing("2:1", start_ms=0, end_ms=1000)

        # Act / Assert
        with patch("subprocess.run") as mock_run:
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "invalid_ayah_timing", 400)
        mock_run.assert_not_called()
        self.assertEqual([f"media/{self.track.audio_file.name}"], self._bucket_keys())

    def test_slice_track_where_ayah_key_is_malformed_should_fail_whole_track(self):
        # Arrange
        self._upload_source_audio()
        self._add_timing("1", start_ms=0, end_ms=1000)

        # Act / Assert
        with patch("subprocess.run") as mock_run:
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "invalid_ayah_timing", 400)
        mock_run.assert_not_called()

    def test_slice_track_where_ffmpeg_fails_should_raise_slicing_failed_and_cleanup_temp_dir(self):
        # Arrange
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        temp_dir = Path(tempfile.mkdtemp(prefix="ayah-slicing-test-"))
        failed = subprocess.CompletedProcess(args=["ffmpeg"], returncode=1, stderr="error: boom\n")

        # Act / Assert
        with (
            patch(
                "apps.content.services.admin.recitation_audio_slicing_service.tempfile.mkdtemp",
                return_value=str(temp_dir),
            ),
            patch("subprocess.run", return_value=failed),
            self.assertLogs("apps.content.services.admin.recitation_audio_slicing_service", level="ERROR") as cm,
        ):
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "slicing_failed", 503)
        # The message must stay generic: raw stderr and temp paths go to the log only
        self.assertEqual("Failed to slice ayah audio with ffmpeg.", ctx.exception.message)
        self.assertNotIn("error: boom", ctx.exception.message)
        self.assertNotIn(str(temp_dir), ctx.exception.message)
        self.assertTrue(any("error: boom" in record.getMessage() for record in cm.records))
        self.assertFalse(temp_dir.exists())
        self.assertEqual([f"media/{self.track.audio_file.name}"], self._bucket_keys())

    def test_slice_track_where_ffmpeg_binary_missing_should_raise_slicing_failed(self):
        # Arrange
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=1000)

        # Act / Assert
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "slicing_failed", 503)

    def test_slice_track_where_source_audio_missing_in_storage_should_raise_storage_error(self):
        # Arrange - nothing uploaded to the bucket for this track
        self._add_timing("1:1", start_ms=0, end_ms=1000)

        # Act / Assert
        with patch("subprocess.run") as mock_run:
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "storage_error", 503)
        mock_run.assert_not_called()
        self.assertEqual([], self._bucket_keys())

    def test_slice_track_where_run_twice_should_overwrite_same_objects_and_stay_idempotent(self):
        # Arrange
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        self._add_timing("1:2", start_ms=1000, end_ms=2000)

        # Act
        with patch("subprocess.run", side_effect=self._fake_ffmpeg(b"x")):
            first = self.service.slice_track(self.track.id)
            second = self.service.slice_track(self.track.id)

        # Assert - deterministic keys overwrite the same objects; no duplicates accumulate
        self.assertEqual(first["keys"], second["keys"])
        slice_keys = [key for key in self._bucket_keys() if "/ayah_" in key]
        self.assertEqual(2, len(slice_keys))

    def test_slice_track_where_ffmpeg_times_out_should_raise_slicing_failed_with_generic_message(self):
        # Arrange
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=1000)

        # Act / Assert
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=30)):
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "slicing_failed", 503)
        self.assertEqual("Slicing ayah audio timed out.", ctx.exception.message)

    def test_slice_track_where_timing_is_sliced_should_build_full_ffmpeg_command(self):
        # Arrange
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=1000)

        # Act
        with patch("subprocess.run", side_effect=self._fake_ffmpeg(b"x")) as mock_run:
            self.service.slice_track(self.track.id)

        # Assert - every flag the slice depends on is present, in one argv list
        cmd = mock_run.call_args.args[0]
        self.assertEqual("ffmpeg", cmd[0])
        for flag in ("-y", "-i", "-ss", "-to", "-af", "-c:a", "libmp3lame"):
            self.assertIn(flag, cmd)
        self.assertTrue(cmd[-1].endswith("001_001.mp3"))

    def test_slice_track_where_ayah_key_has_leading_zeros_should_fail_whole_track(self):
        # Arrange - "1:01" and "01:1" parse numerically but are non-canonical; accepting
        # them would let two distinct keys alias the same slice object silently
        for non_canonical in ("1:01", "01:1"):
            with self.subTest(ayah_key=non_canonical):
                self.track.ayah_timings.all().delete()
                self._upload_source_audio()
                self._add_timing(non_canonical, start_ms=0, end_ms=1000)

                # Act / Assert
                with patch("subprocess.run") as mock_run:
                    with self.assertRaises(ItqanError) as ctx:
                        self.service.slice_track(self.track.id)

                self._assert_slicing_rejected(ctx, "invalid_ayah_timing", 400)
                mock_run.assert_not_called()
                self.assertEqual([f"media/{self.track.audio_file.name}"], self._bucket_keys())

    def test_slice_track_where_track_duration_is_zero_should_fail_whole_track_before_io(self):
        # Arrange - a track whose duration was never computed cannot have valid
        # timings, so the whole track is rejected before any storage/ffmpeg work
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        self.track.duration_ms = 0
        self.track.save(update_fields=["duration_ms"])

        # Act / Assert
        with patch("subprocess.run") as mock_run:
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "invalid_ayah_timing", 400)
        mock_run.assert_not_called()
        self.assertEqual([f"media/{self.track.audio_file.name}"], self._bucket_keys())

    def test_slice_track_where_end_ms_equals_track_duration_should_slice(self):
        # Arrange - the last ayah legitimately ends exactly at the track boundary
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=5000)  # track duration_ms = 5000

        # Act
        with patch("subprocess.run", side_effect=self._fake_ffmpeg(b"x")) as mock_run:
            result = self.service.slice_track(self.track.id)

        # Assert
        self.assertEqual(1, result["sliced"])
        mock_run.assert_called_once()
        slice_keys = [key for key in self._bucket_keys() if "/ayah_" in key]
        self.assertEqual(1, len(slice_keys))

    def test_slice_track_where_slicing_succeeds_should_remove_temporary_directory(self):
        # Arrange
        self._upload_source_audio()
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        temp_dir = Path(tempfile.mkdtemp(prefix="ayah-slicing-test-"))

        # Act
        with (
            patch(
                "apps.content.services.admin.recitation_audio_slicing_service.tempfile.mkdtemp",
                return_value=str(temp_dir),
            ),
            patch("subprocess.run", side_effect=self._fake_ffmpeg(b"x")),
        ):
            self.service.slice_track(self.track.id)

        # Assert
        self.assertFalse(temp_dir.exists())

    def test_slice_track_where_source_download_fails_should_remove_temporary_directory(self):
        # Arrange - nothing uploaded to the bucket, so get_object raises NoSuchKey
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        temp_dir = Path(tempfile.mkdtemp(prefix="ayah-slicing-test-"))

        # Act / Assert
        with patch(
            "apps.content.services.admin.recitation_audio_slicing_service.tempfile.mkdtemp",
            return_value=str(temp_dir),
        ):
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "storage_error", 503)
        self.assertFalse(temp_dir.exists())

    def test_slice_track_where_upload_fails_should_raise_storage_error_with_generic_message(self):
        # Arrange - put_object raising ClientError (e.g. AccessDenied) must become a
        # generic storage_error, not leak the underlying detail
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        failing_s3 = self._failing_storage_client(
            upload_error=ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "secret denied detail"}}, "PutObject"
            )
        )

        # Act / Assert
        with patch.object(self.service, "_get_s3_client", return_value=failing_s3):
            with patch("subprocess.run", side_effect=self._fake_ffmpeg(b"x")):
                with self.assertRaises(ItqanError) as ctx:
                    self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "storage_error", 503)
        self.assertNotIn("denied", ctx.exception.message)
        self.assertNotIn("AccessDenied", ctx.exception.message)

    def test_slice_track_where_download_connection_fails_should_raise_storage_error_with_generic_message(self):
        # Arrange - connection-level failures are BotoCoreError, not ClientError
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        failing_s3 = self._failing_storage_client(
            download_error=EndpointConnectionError(endpoint_url="http://internal-r2.local:5000")
        )

        # Act / Assert
        with patch.object(self.service, "_get_s3_client", return_value=failing_s3):
            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "storage_error", 503)
        self.assertNotIn("internal-r2.local", ctx.exception.message)

    def test_slice_track_where_upload_connection_fails_should_raise_storage_error_with_generic_message(self):
        # Arrange
        self._add_timing("1:1", start_ms=0, end_ms=1000)
        failing_s3 = self._failing_storage_client(
            upload_error=EndpointConnectionError(endpoint_url="http://internal-r2.local:5000")
        )

        # Act / Assert
        with patch.object(self.service, "_get_s3_client", return_value=failing_s3):
            with patch("subprocess.run", side_effect=self._fake_ffmpeg(b"x")):
                with self.assertRaises(ItqanError) as ctx:
                    self.service.slice_track(self.track.id)

        self._assert_slicing_rejected(ctx, "storage_error", 503)
        self.assertNotIn("internal-r2.local", ctx.exception.message)
