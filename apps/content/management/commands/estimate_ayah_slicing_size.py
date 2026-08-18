"""
Read-only storage sizing estimate for ayah audio slicing (issue #412).

Before committing to a full precompute of per-ayah audio files, run:

    python manage.py estimate_ayah_slicing_size

The command reports object counts, source bytes and an estimated output
footprint from current database rows only - no storage calls, no broker, no
writes. Optional environment inputs (see config/settings/base.py) enable a
fallback output bitrate, storage/egress pricing and warning thresholds; when
they are unset the corresponding sections are omitted rather than invented.

Estimate method: a per-track bitrate proxy is derived from the stored source
metadata (size_bytes * 8 / duration_ms, i.e. bits per millisecond of source)
and each slice is estimated as timing_duration_ms * bitrate / 8. That scales
the source byte density linearly by slice duration - a reasonable proxy for a
libmp3lame re-encode that keeps roughly the source's byte density, and the
best available given the track model stores only size_bytes and duration_ms.
Tracks without usable duration/size fall back to the configured
AYAH_SLICING_ESTIMATED_OUTPUT_BITRATE (bits per second, converted to the same
per-millisecond unit) or are reported as not estimated.

Timing rows that the slicer would reject (non-canonical ayah keys or
out-of-range start/end offsets, per the shared eligibility contract in
RecitationAudioSlicingService) are excluded from the expected object count and
byte estimate and reported separately; the raw row count stays visible.
The slicer also rejects a track as a whole when ANY of its timings is invalid,
so every row of such a track is excluded from the estimate too, not just the
invalid row(s). Cost math uses decimal GB (1 GB = 1,000,000,000 bytes) because
Cloudflare R2 rates are quoted per decimal GB; human-readable size display
stays binary GiB.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.content.models import Asset, CategoryChoice, RecitationAyahTiming, RecitationFolder, RecitationSurahTrack
from apps.content.services.admin.recitation_audio_slicing_service import timing_eligibility_reason

# Decimal GB for cost math: Cloudflare R2 prices are quoted per decimal GB.
DECIMAL_GB_BYTES = 1_000_000_000


def estimate_slicing_size() -> dict[str, Any]:
    """Compute the ayah-slicing sizing estimate from current database rows."""
    asset_count = Asset.objects.filter(category=CategoryChoice.RECITATION).count()
    folder_count = RecitationFolder.objects.count()
    track_count = RecitationSurahTrack.objects.count()
    timing_count = RecitationAyahTiming.objects.count()

    track_bitrate: dict[int, float | None] = {}
    track_duration: dict[int, int] = {}
    track_surah: dict[int, int] = {}
    total_source_bytes = 0
    for track_id, size_bytes, duration_ms, surah_number in RecitationSurahTrack.objects.values_list(
        "id", "size_bytes", "duration_ms", "surah_number"
    ):
        total_source_bytes += size_bytes
        track_duration[track_id] = duration_ms
        track_surah[track_id] = surah_number
        if size_bytes and duration_ms:
            track_bitrate[track_id] = size_bytes * 8 / duration_ms
        else:
            track_bitrate[track_id] = None

    # A 0/None setting means "not configured" (base.py uses 0 as its decouple sentinel).
    fallback_bps = settings.AYAH_SLICING_ESTIMATED_OUTPUT_BITRATE or None

    estimated_output_bytes = 0
    estimated_timing_count = 0
    unestimated_timing_count = 0
    unestimated_track_ids: set[int] = set()
    fallback_used_timing_count = 0
    invalid_timing_count = 0
    invalid_timing_reasons: dict[str, int] = {}
    invalid_track_ids: set[int] = set()
    rejected_track_timing_count = 0

    timing_rows = list(
        RecitationAyahTiming.objects.values_list("track_id", "ayah_key", "start_ms", "end_ms", "duration_ms")
    )

    # Phase 1 - the slicer rejects a track as a whole when any of its timings is
    # invalid, so first find every track with at least one ineligible row and
    # tally the row-level reasons (single source of truth: timing_eligibility_reason).
    rows_with_reason: list[tuple[int, str, int, int, int, str | None]] = []
    for track_id, ayah_key, start_ms, end_ms, timing_duration_ms in timing_rows:
        reason = timing_eligibility_reason(ayah_key, start_ms, end_ms, track_surah[track_id], track_duration[track_id])
        rows_with_reason.append((track_id, ayah_key, start_ms, end_ms, timing_duration_ms, reason))
        if reason is not None:
            invalid_timing_count += 1
            invalid_timing_reasons[reason] = invalid_timing_reasons.get(reason, 0) + 1
            invalid_track_ids.add(track_id)

    # Phase 2 - only fully eligible tracks contribute objects/bytes; every row of a
    # rejected track is excluded (otherwise-valid rows are counted separately).
    for track_id, _ayah_key, _start_ms, _end_ms, timing_duration_ms, reason in rows_with_reason:
        if track_id in invalid_track_ids:
            if reason is None:
                rejected_track_timing_count += 1
            continue
        bitrate = track_bitrate.get(track_id)
        used_fallback = False
        if bitrate is None and fallback_bps:
            bitrate = fallback_bps / 1000
            used_fallback = True
        if bitrate:
            estimated_output_bytes += timing_duration_ms * bitrate / 8
            estimated_timing_count += 1
            if used_fallback:
                fallback_used_timing_count += 1
        else:
            unestimated_timing_count += 1
            unestimated_track_ids.add(track_id)

    expected_object_count = timing_count - invalid_timing_count - rejected_track_timing_count
    storage_cost_per_gb = settings.R2_STORAGE_COST_PER_GB_MONTH or None
    egress_cost_per_gb = settings.R2_EGRESS_COST_PER_GB or None
    estimated_storage_cost_per_month = (
        round(estimated_output_bytes / DECIMAL_GB_BYTES * storage_cost_per_gb, 4)
        if storage_cost_per_gb is not None
        else None
    )
    estimated_egress_cost = (
        round(estimated_output_bytes / DECIMAL_GB_BYTES * egress_cost_per_gb, 4)
        if egress_cost_per_gb is not None
        else None
    )

    warn_object_count = settings.AYAH_SLICING_WARN_OBJECT_COUNT or None
    warn_estimated_bytes = settings.AYAH_SLICING_WARN_ESTIMATED_BYTES or None

    return {
        "asset_count": asset_count,
        "folder_count": folder_count,
        "track_count": track_count,
        "timing_count": timing_count,
        "invalid_timing_count": invalid_timing_count,
        "invalid_timing_reasons": invalid_timing_reasons,
        "invalid_track_count": len(invalid_track_ids),
        "rejected_track_timing_count": rejected_track_timing_count,
        "expected_object_count": expected_object_count,
        "total_source_bytes": total_source_bytes,
        "estimated_output_bytes": int(round(estimated_output_bytes)),
        "estimated_timing_count": estimated_timing_count,
        "unestimated_timing_count": unestimated_timing_count,
        "unestimated_track_count": len(unestimated_track_ids),
        "fallback_bitrate_bps": fallback_bps,
        "fallback_used_timing_count": fallback_used_timing_count,
        "storage_cost_per_gb_month": storage_cost_per_gb,
        "egress_cost_per_gb": egress_cost_per_gb,
        "estimated_storage_cost_per_month": estimated_storage_cost_per_month,
        "estimated_egress_cost": estimated_egress_cost,
        "warn_object_count": warn_object_count,
        "warn_estimated_bytes": warn_estimated_bytes,
        "object_threshold_exceeded": warn_object_count is not None and expected_object_count > warn_object_count,
        "bytes_threshold_exceeded": warn_estimated_bytes is not None
        and int(round(estimated_output_bytes)) > warn_estimated_bytes,
    }


class Command(BaseCommand):
    help = "Report the storage sizing estimate for precomputing per-ayah audio slices (read-only)."

    def handle(self, *args: Any, **options: Any) -> None:
        report = estimate_slicing_size()
        out = self.stdout

        def line(label: str, value: str) -> None:
            out.write(f"{label:<42}{value}")

        out.write(self.style.SUCCESS("Recitation ayah-slicing storage sizing estimate"))
        line("Recitation assets:", str(report["asset_count"]))
        line("Recitation folders:", str(report["folder_count"]))
        line("Surah tracks:", str(report["track_count"]))
        line("Ayah timing rows (raw):", str(report["timing_count"]))
        if report["invalid_timing_count"]:
            out.write(
                self.style.WARNING(
                    f"NOTE: {report['invalid_timing_count']} timing row(s) rejected by the slicer's "
                    "eligibility rules; excluded from the estimate below."
                )
            )
            for reason, count in sorted(report["invalid_timing_reasons"].items()):
                out.write(f"    - {reason}: {count}")
        if report["invalid_track_count"]:
            out.write(
                self.style.WARNING(
                    f"NOTE: {report['invalid_track_count']} track(s) rejected as a whole because at least "
                    f"one timing is invalid; {report['rejected_track_timing_count']} otherwise-valid "
                    "timing row(s) on them are also excluded."
                )
            )
        line("Expected sliced objects:", str(report["expected_object_count"]))
        line(
            "Total source audio bytes:",
            self._format_bytes(report["total_source_bytes"]),
        )
        line(
            "Estimated output bytes:",
            self._format_bytes(report["estimated_output_bytes"]),
        )

        if report["unestimated_timing_count"]:
            out.write(
                self.style.WARNING(
                    "NOTE: "
                    f"{report['unestimated_timing_count']} timing row(s) on "
                    f"{report['unestimated_track_count']} track(s) not estimated "
                    "(no source size/duration and AYAH_SLICING_ESTIMATED_OUTPUT_BITRATE unset)."
                )
            )
        if report["fallback_used_timing_count"]:
            out.write(
                self.style.WARNING(
                    "NOTE: fallback AYAH_SLICING_ESTIMATED_OUTPUT_BITRATE="
                    f"{report['fallback_bitrate_bps']} bps used for "
                    f"{report['fallback_used_timing_count']} timing row(s)."
                )
            )

        if report["storage_cost_per_gb_month"] is not None or report["egress_cost_per_gb"] is not None:
            if report["estimated_storage_cost_per_month"] is not None:
                line(
                    "Estimated storage cost:",
                    f"${report['estimated_storage_cost_per_month']:.4f}/month "
                    f"(at ${report['storage_cost_per_gb_month']:.4f}/GB/month, decimal GB)",
                )
            if report["estimated_egress_cost"] is not None:
                line(
                    "Estimated egress cost:",
                    f"${report['estimated_egress_cost']:.4f} "
                    f"(at ${report['egress_cost_per_gb']:.4f}/GB, decimal GB, one-time full download)",
                )
        else:
            out.write(
                self.style.WARNING(
                    "R2 pricing not configured (R2_STORAGE_COST_PER_GB_MONTH / "
                    "R2_EGRESS_COST_PER_GB unset); cost calculations omitted."
                )
            )

        if report["object_threshold_exceeded"]:
            out.write(
                self.style.ERROR(
                    "WARNING: EXCEEDS configured threshold "
                    f"(expected objects: {report['expected_object_count']} > {report['warn_object_count']}) "
                    "- revisit full precompute vs lazy slicing."
                )
            )
        if report["bytes_threshold_exceeded"]:
            out.write(
                self.style.ERROR(
                    "WARNING: EXCEEDS configured threshold "
                    f"(estimated bytes: {report['estimated_output_bytes']} > {report['warn_estimated_bytes']}) "
                    "- revisit full precompute vs lazy slicing."
                )
            )
        if report["warn_object_count"] is None and report["warn_estimated_bytes"] is None:
            out.write("Thresholds not configured; no precompute-vs-lazy warning issued.")

    @staticmethod
    def _format_bytes(n: int) -> str:
        # Binary GiB for human-readable sizes; cost math uses decimal GB (see DECIMAL_GB_BYTES).
        return f"{n:,} bytes ({n / (1 << 30):.2f} GiB, binary)"
