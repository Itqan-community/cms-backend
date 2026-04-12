from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from apps.content.repositories.recitation_track import RecitationTrackRepository
from apps.core.ninja_utils.errors import ItqanError
from apps.mixins.recitations_helpers import extract_surah_number_from_mp3_filename


@dataclass
class FileValidationResult:
    filename: str
    status: Literal["valid", "skip", "invalid"]


@dataclass
class TrackUploadValidationResult:
    asset_id: int
    status: Literal["valid", "invalid"]
    message: str
    files: list[FileValidationResult]


class ValidateRecitationTracksUploadService:
    def __init__(self, repo: RecitationTrackRepository | None = None) -> None:
        self.repo = repo or RecitationTrackRepository()

    def validate(self, *, asset_id: int, filenames: list[str]) -> TrackUploadValidationResult:
        existing_surah_numbers = self.repo.get_recitation_tracks_surah_numbers_by_asset_id(asset_id)
        seen_filenames: set[str] = set()
        files: list[FileValidationResult] = []

        for filename in filenames:
            status: Literal["valid", "skip", "invalid"] = "valid"

            if filename in seen_filenames:
                status = "invalid"
            elif not filename.endswith(".mp3"):
                status = "invalid"
            else:
                try:
                    surah_number = extract_surah_number_from_mp3_filename(filename)
                except ItqanError:
                    status = "invalid"
                else:
                    if surah_number in existing_surah_numbers:
                        status = "skip"

            seen_filenames.add(filename)
            files.append(FileValidationResult(filename=filename, status=status))

        if not filenames:
            top_status: Literal["valid", "invalid"] = "invalid"
            message = "No files were submitted. Select at least one MP3 file and try again."

        elif all(f.status == "skip" for f in files):
            top_status = "invalid"
            message = "All submitted files already have uploaded tracks. No new files to upload."

        elif any(f.status == "invalid" for f in files):
            top_status = "invalid"
            message = "Some files are invalid (either for naming or extension or duplication). Fix them and try again."

        elif any(f.status == "valid" for f in files) and any(f.status == "skip" for f in files):
            top_status = "valid"
            message = "Some files will be skipped because their tracks already exist."

        else:
            top_status = "valid"
            message = "All files are valid and ready to upload."

        return TrackUploadValidationResult(
            asset_id=asset_id,
            status=top_status,
            message=message,
            files=files,
        )
