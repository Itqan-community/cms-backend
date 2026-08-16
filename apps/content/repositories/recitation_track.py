from __future__ import annotations

from datetime import datetime

from django.db.models import Q

from apps.content.models import RecitationSurahTrack


class RecitationTrackRepository:
    def __init__(self) -> None:
        self.model = RecitationSurahTrack

    def get_recitation_tracks_surah_numbers_by_folder_id(self, folder_id: int) -> set[int]:
        """
        Return the surah numbers already uploaded into the given folder.

        Scoped to the folder rather than the asset: the same surah legitimately
        exists once per variant, so an asset-wide check would wrongly report a
        surah as already uploaded when only a *different* variant has it.
        """
        return set(self.model.objects.filter(folder_id=folder_id).values_list("surah_number", flat=True))

    def get_recitation_tracks_by_ids(
        self, track_ids: list[int], publisher_q: Q | None = None
    ) -> list[RecitationSurahTrack]:
        """Return tracks whose IDs are in track_ids, optionally scoped by publisher membership via the parent asset."""
        qs = self.model.objects.filter(id__in=track_ids)
        if publisher_q is not None:
            qs = qs.filter(publisher_q)
        return list(qs)

    def create_recitation_track(
        self,
        asset_id: int,
        folder_id: int,
        surah_number: int,
        audio_file: str,
        original_filename: str | None = None,
        duration_ms: int = 0,
        size_bytes: int = 0,
        upload_finished_at: datetime | None = None,
    ) -> RecitationSurahTrack:
        """Persist a new RecitationSurahTrack row and return it."""
        return self.model.objects.create(
            asset_id=asset_id,
            folder_id=folder_id,
            surah_number=surah_number,
            audio_file=audio_file,
            original_filename=original_filename,
            duration_ms=duration_ms,
            size_bytes=size_bytes,
            upload_finished_at=upload_finished_at,
        )

    def delete_recitation_tracks(self, tracks: list[RecitationSurahTrack]) -> None:
        """Delete tracks one by one (triggering model signals and mixins)."""
        for track in tracks:
            track.delete()
