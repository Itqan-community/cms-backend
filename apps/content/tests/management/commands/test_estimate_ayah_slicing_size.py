from __future__ import annotations

import io

from django.core.management import call_command
from django.test import override_settings
from model_bakery import baker

from apps.content.management.commands.estimate_ayah_slicing_size import estimate_slicing_size
from apps.content.models import (
    Asset,
    CategoryChoice,
    RecitationAyahTiming,
    RecitationFolder,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
)
from apps.core.tests.base import BaseTestCase


class EstimateAyahSlicingSizeCommandTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=baker.make(Reciter, name="Test Reciter", slug="test-reciter"),
            riwayah=baker.make(Riwayah, name="Test Riwayah"),
        )
        self.default_folder = RecitationFolder.objects.get(asset=self.asset, is_default=True)
        self.echo_folder = RecitationFolder.objects.create(asset=self.asset, name="Echo", slug="echo")

    def _make_track(self, folder, surah_number, size_bytes, duration_ms) -> RecitationSurahTrack:
        return RecitationSurahTrack.objects.create(
            asset=self.asset,
            folder=folder,
            surah_number=surah_number,
            audio_file="",
            size_bytes=size_bytes,
            duration_ms=duration_ms,
        )

    def _make_timing(self, track, ayah_number, start_ms, end_ms) -> RecitationAyahTiming:
        return RecitationAyahTiming.objects.create(
            track=track,
            ayah_key=f"{track.surah_number}:{ayah_number}",
            start_ms=start_ms,
            end_ms=end_ms,
        )

    def _run_command(self) -> str:
        out = io.StringIO()
        call_command("estimate_ayah_slicing_size", stdout=out)
        return out.getvalue()

    def test_counts_across_multiple_folders_and_tracks(self):
        # Arrange - one asset, two folders, one track each, three timings total
        clear_track = self._make_track(self.default_folder, 1, size_bytes=32000, duration_ms=4000)
        echo_track = self._make_track(self.echo_folder, 1, size_bytes=64000, duration_ms=8000)
        self._make_timing(clear_track, 1, start_ms=0, end_ms=1000)
        self._make_timing(clear_track, 2, start_ms=1000, end_ms=2000)
        self._make_timing(echo_track, 1, start_ms=0, end_ms=1500)

        # Act
        report = estimate_slicing_size()

        # Assert - every count comes from current DB rows
        self.assertEqual(1, report["asset_count"])
        self.assertEqual(2, report["folder_count"])
        self.assertEqual(2, report["track_count"])
        self.assertEqual(3, report["timing_count"])

    def test_expected_object_count_equals_valid_timing_row_count(self):
        # Arrange - all rows valid, so raw == valid == expected
        track = self._make_track(self.default_folder, 1, size_bytes=32000, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)
        self._make_timing(track, 2, start_ms=1000, end_ms=2000)

        # Act / Assert
        report = estimate_slicing_size()
        self.assertEqual(report["timing_count"], report["expected_object_count"])
        self.assertEqual(0, report["invalid_timing_count"])
        self.assertEqual(2, report["expected_object_count"])

    def test_invalid_timing_rows_are_excluded_from_estimate_and_reported(self):
        # Arrange - one valid row and one of each rejected range/key shape
        track = self._make_track(self.default_folder, 1, size_bytes=32000, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)
        RecitationAyahTiming.objects.create(track=track, ayah_key="1:2", start_ms=1000, end_ms=1000)
        RecitationAyahTiming.objects.create(track=track, ayah_key="1:3", start_ms=2000, end_ms=1500)
        RecitationAyahTiming.objects.create(track=track, ayah_key="1:4", start_ms=3000, end_ms=5000)
        RecitationAyahTiming.objects.create(track=track, ayah_key="1:05", start_ms=0, end_ms=1000)

        # Act
        report = estimate_slicing_size()
        output = self._run_command()

        # Assert - raw count kept, invalid rows excluded from objects/bytes/reasons listed
        self.assertEqual(5, report["timing_count"])
        self.assertEqual(4, report["invalid_timing_count"])
        self.assertEqual(1, report["expected_object_count"])
        self.assertEqual(8000, report["estimated_output_bytes"])
        self.assertEqual(1, report["estimated_timing_count"])
        self.assertIn("end_ms must be greater than start_ms", report["invalid_timing_reasons"])
        self.assertIn("end_ms must not exceed the track duration", report["invalid_timing_reasons"])
        self.assertIn("invalid or non-canonical ayah key", report["invalid_timing_reasons"])
        self.assertIn("rejected by the slicer", output)

    @override_settings(AYAH_SLICING_WARN_OBJECT_COUNT=1)
    def test_object_threshold_uses_valid_count_not_raw_rows(self):
        # Arrange - 4 raw timing rows, only 1 eligible, threshold of 1
        track = self._make_track(self.default_folder, 1, size_bytes=32000, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)
        RecitationAyahTiming.objects.create(track=track, ayah_key="1:2", start_ms=1000, end_ms=1000)
        RecitationAyahTiming.objects.create(track=track, ayah_key="1:3", start_ms=2000, end_ms=1500)
        RecitationAyahTiming.objects.create(track=track, ayah_key="1:4", start_ms=3000, end_ms=5000)

        # Act
        report = estimate_slicing_size()
        output = self._run_command()

        # Assert - eligible count (1) is not > 1, so no warning despite 4 raw rows
        self.assertEqual(4, report["timing_count"])
        self.assertEqual(1, report["expected_object_count"])
        self.assertFalse(report["object_threshold_exceeded"])
        self.assertNotIn("EXCEEDS", output)

    def test_total_source_bytes_are_summed(self):
        # Arrange
        self._make_track(self.default_folder, 1, size_bytes=32000, duration_ms=4000)
        self._make_track(self.echo_folder, 1, size_bytes=64000, duration_ms=8000)

        # Act / Assert
        self.assertEqual(96000, estimate_slicing_size()["total_source_bytes"])

    def test_derived_bitrate_math(self):
        # Arrange - 32000 bytes over 4000 ms -> 64 bits per ms; a 1000 ms slice -> 8000 bytes
        track = self._make_track(self.default_folder, 1, size_bytes=32000, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)

        # Act
        report = estimate_slicing_size()

        # Assert
        self.assertEqual(8000, report["estimated_output_bytes"])
        self.assertEqual(1, report["estimated_timing_count"])
        self.assertEqual(0, report["unestimated_timing_count"])
        self.assertEqual(0, report["unestimated_track_count"])

    @override_settings(AYAH_SLICING_ESTIMATED_OUTPUT_BITRATE=64000)
    def test_fallback_bitrate_when_derivation_impossible(self):
        # Arrange - usable duration but no source size -> no derived bitrate; 64000 bps fallback
        track = self._make_track(self.default_folder, 1, size_bytes=0, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)

        # Act
        report = estimate_slicing_size()

        # Assert - fallback applies only where derivation is impossible
        self.assertEqual(8000, report["estimated_output_bytes"])
        self.assertEqual(1, report["estimated_timing_count"])
        self.assertEqual(0, report["unestimated_timing_count"])
        self.assertEqual(1, report["fallback_used_timing_count"])
        self.assertEqual(64000, report["fallback_bitrate_bps"])

    def test_missing_fallback_reports_unestimated_timings(self):
        # Arrange - no fallback configured and the track has no usable size (but a valid duration)
        track = self._make_track(self.default_folder, 1, size_bytes=0, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)

        # Act
        report = estimate_slicing_size()
        output = self._run_command()

        # Assert - nothing invented; timings reported as not estimated
        self.assertEqual(0, report["estimated_output_bytes"])
        self.assertEqual(0, report["estimated_timing_count"])
        self.assertEqual(1, report["unestimated_timing_count"])
        self.assertEqual(1, report["unestimated_track_count"])
        self.assertIn("not estimated", output)

    @override_settings(
        AYAH_SLICING_WARN_OBJECT_COUNT=2,
        AYAH_SLICING_WARN_ESTIMATED_BYTES=100,
    )
    def test_threshold_exceeded_warning(self):
        # Arrange - 3 timings and 8000 estimated bytes against thresholds of 2 and 100
        track = self._make_track(self.default_folder, 1, size_bytes=32000, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)
        self._make_timing(track, 2, start_ms=1000, end_ms=2000)
        self._make_timing(track, 3, start_ms=2000, end_ms=3000)

        # Act
        report = estimate_slicing_size()
        output = self._run_command()

        # Assert - both thresholds exceeded and the revisit signal is printed
        self.assertTrue(report["object_threshold_exceeded"])
        self.assertTrue(report["bytes_threshold_exceeded"])
        self.assertIn("EXCEEDS configured threshold", output)
        self.assertIn("revisit full precompute vs lazy slicing", output)

    @override_settings(
        AYAH_SLICING_WARN_OBJECT_COUNT=99999,
        AYAH_SLICING_WARN_ESTIMATED_BYTES=999999999,
    )
    def test_threshold_not_exceeded(self):
        # Arrange
        track = self._make_track(self.default_folder, 1, size_bytes=32000, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)

        # Act
        report = estimate_slicing_size()
        output = self._run_command()

        # Assert
        self.assertFalse(report["object_threshold_exceeded"])
        self.assertFalse(report["bytes_threshold_exceeded"])
        self.assertNotIn("EXCEEDS", output)

    def test_cost_omitted_when_pricing_unset(self):
        # Arrange
        track = self._make_track(self.default_folder, 1, size_bytes=32000, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)

        # Act
        report = estimate_slicing_size()
        output = self._run_command()

        # Assert - no pricing configured: costs omitted and stated explicitly
        self.assertIsNone(report["estimated_storage_cost_per_month"])
        self.assertIsNone(report["estimated_egress_cost"])
        self.assertIn("R2 pricing not configured", output)

    @override_settings(
        R2_STORAGE_COST_PER_GB_MONTH=0.015,
        R2_EGRESS_COST_PER_GB=0.09,
    )
    def test_cost_calculated_when_pricing_configured(self):
        # Arrange - 800000000 estimated bytes -> 0.8 decimal GB
        track = self._make_track(self.default_folder, 1, size_bytes=3200000000, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)

        # Act
        report = estimate_slicing_size()
        output = self._run_command()

        # Assert - decimal GB (1 GB = 1e9 bytes): 0.8 * 0.015 and 0.8 * 0.09
        self.assertEqual(800000000, report["estimated_output_bytes"])
        self.assertAlmostEqual(0.012, report["estimated_storage_cost_per_month"], places=4)
        self.assertAlmostEqual(0.072, report["estimated_egress_cost"], places=4)
        self.assertIn("Estimated storage cost", output)
        self.assertIn("Estimated egress cost", output)
        self.assertIn("decimal GB", output)
        self.assertIn("/GB/month", output)
        self.assertNotIn("GiB/month", output)

    def test_command_performs_no_writes(self):
        # Arrange
        track = self._make_track(self.default_folder, 1, size_bytes=32000, duration_ms=4000)
        self._make_timing(track, 1, start_ms=0, end_ms=1000)
        before = {
            "assets": Asset.objects.count(),
            "folders": RecitationFolder.objects.count(),
            "tracks": RecitationSurahTrack.objects.count(),
            "timings": RecitationAyahTiming.objects.count(),
            "timing_pks": list(RecitationAyahTiming.objects.values_list("pk", flat=True)),
        }

        # Act
        self._run_command()

        # Assert - read-only: every count and row set is untouched
        self.assertEqual(before["assets"], Asset.objects.count())
        self.assertEqual(before["folders"], RecitationFolder.objects.count())
        self.assertEqual(before["tracks"], RecitationSurahTrack.objects.count())
        self.assertEqual(before["timings"], RecitationAyahTiming.objects.count())
        self.assertEqual(before["timing_pks"], list(RecitationAyahTiming.objects.values_list("pk", flat=True)))
