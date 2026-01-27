from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction

from apps.content.models import Asset, RecitationSurahTrack
from apps.mixins.recitations_helpers import extract_surah_number_from_mp3_filename


def bulk_upload_recitation_audio_tracks(asset_id: int, files: Iterable) -> dict:
    """
    Upload multiple MP3 files as RecitationSurahTrack rows for the given asset.
    - Skips duplicates within selection and already-existing tracks in DB.
    - Runs in a single atomic transaction; on error, attempts best-effort cleanup by storage.
    Returns stats dict: {created, filename_errors, skipped_duplicates, other_errors, duplicate_details, other_error_details}
    """
    asset = Asset.objects.get(pk=asset_id)

    created = 0
    filename_errors = 0
    skipped_duplicates = 0
    duplicate_details: list[str] = []
    other_errors = 0
    other_error_details: list[str] = []
    uploaded_file_names: list[str] = []  # for best-effort cleanup on rollback
    seen_surahs: set[int] = set()  # duplicates within the same selection

    try:
        with transaction.atomic():
            for f in files:
                try:
                    surah_number = extract_surah_number_from_mp3_filename(f.name)
                except ValueError:
                    filename_errors += 1
                    continue

                if surah_number in seen_surahs:
                    skipped_duplicates += 1
                    duplicate_details.append(f"{f.name} (duplicate in selection)")
                    continue
                seen_surahs.add(surah_number)

                if RecitationSurahTrack.objects.filter(asset_id=asset.id, surah_number=surah_number).exists():
                    skipped_duplicates += 1
                    duplicate_details.append(f"{f.name} (already exists)")
                    continue

                obj = RecitationSurahTrack.objects.create(
                    asset=asset,
                    surah_number=surah_number,
                    audio_file=f,
                    original_filename=getattr(f, "name", None),
                )
                try:
                    if obj.audio_file and getattr(obj.audio_file, "name", None):
                        uploaded_file_names.append(obj.audio_file.name)
                except Exception:
                    pass
                created += 1
    except Exception as e:
        # Best-effort cleanup of any uploaded files when the DB transaction rolls back
        try:
            from django.core.files.storage import default_storage

            for name in uploaded_file_names:
                try:
                    default_storage.delete(name)
                except Exception:
                    pass
        except Exception:
            pass

        other_errors += 1
        other_error_details.append(str(e))

    return {
        "created": created,
        "filename_errors": filename_errors,
        "skipped_duplicates": skipped_duplicates,
        "other_errors": other_errors,
        "duplicate_details": duplicate_details,
        "other_error_details": other_error_details,
    }
