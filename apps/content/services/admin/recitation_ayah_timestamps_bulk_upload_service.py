from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction

from apps.content.models import Asset, RecitationAyahTiming, RecitationSurahTrack
from apps.content.services.ayah_timings_import import parse_json_bytes


def bulk_upload_recitation_ayah_timestamps(asset_id: int, files: Iterable) -> dict:
    """
    Import ayah timings JSON files for a given asset.
    - files: iterable of UploadedFile objects (each file for a surah)
    Behavior:
    - Create new timings when missing
    - Update existing timings only when values differ
    - Skip when identical
    All changes are executed within a single atomic transaction.
    Returns a stats dict with counts and details.
    """
    asset = Asset.objects.get(pk=asset_id)

    # Preload tracks for the asset
    tracks = RecitationSurahTrack.objects.filter(asset=asset).only("id", "surah_number")
    track_by_surah = {t.surah_number: t for t in tracks}

    created_total = 0
    updated_total = 0
    skipped_total = 0
    missing_tracks: list[int] = []
    file_errors: list[str] = []

    try:
        with transaction.atomic():
            for f in files:
                try:
                    surah_number, rows = parse_json_bytes(f.read())
                except Exception as e:
                    file_errors.append(f"{f.name}: {e}")
                    continue

                track = track_by_surah.get(surah_number)
                if not track:
                    missing_tracks.append(surah_number)
                    continue

                existing = {
                    t.ayah_key: t
                    for t in RecitationAyahTiming.objects.filter(track=track).only(
                        "id", "ayah_key", "start_ms", "end_ms", "duration_ms"
                    )
                }

                to_create: list[RecitationAyahTiming] = []
                to_update: list[RecitationAyahTiming] = []

                for row in rows:
                    obj: RecitationAyahTiming | None = existing.get(row.ayah_key)
                    if not obj:
                        to_create.append(
                            RecitationAyahTiming(
                                track=track,
                                ayah_key=row.ayah_key,
                                start_ms=row.start_ms,
                                end_ms=row.end_ms,
                                duration_ms=row.duration_ms,
                            )
                        )
                        continue

                    changed = (
                        obj.start_ms != row.start_ms or obj.end_ms != row.end_ms or obj.duration_ms != row.duration_ms
                    )
                    if changed:
                        obj.start_ms = row.start_ms
                        obj.end_ms = row.end_ms
                        obj.duration_ms = row.duration_ms
                        to_update.append(obj)
                    else:
                        skipped_total += 1

                if to_create:
                    RecitationAyahTiming.objects.bulk_create(to_create, batch_size=2000)
                if to_update:
                    RecitationAyahTiming.objects.bulk_update(
                        to_update, fields=["start_ms", "end_ms", "duration_ms"], batch_size=2000
                    )

                created_total += len(to_create)
                updated_total += len(to_update)

    except Exception as e:
        file_errors.append(str(e))

    return {
        "created_total": created_total,
        "updated_total": updated_total,
        "skipped_total": skipped_total,
        "missing_tracks": sorted(set(missing_tracks)),
        "file_errors": file_errors,
    }
