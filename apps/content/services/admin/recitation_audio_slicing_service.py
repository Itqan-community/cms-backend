from __future__ import annotations

import logging
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.content.models import RecitationSurahTrack
from apps.core.ninja_utils.errors import ItqanError

if TYPE_CHECKING:
    from apps.content.models import RecitationAyahTiming

logger = logging.getLogger(__name__)

FADE_DURATION_SECONDS = 0.02
# Per-ayah ffmpeg deadline: matches the repo's external-call convention of 30s
# (see _REQUEST_TIMEOUT_SECONDS in usage_tracking clients) and stays well below
# the 60s CELERY_TASK_SOFT_TIME_LIMIT so a stalled slice fails as slicing_failed
# instead of hanging the worker.
FFMPEG_SLICE_TIMEOUT_SECONDS = 30


def _split_ayah_key(ayah_key: str) -> tuple[str, str] | None:
    """Split a "surah:ayah" key into its two parts, or None when either part is not decimal."""
    parts = ayah_key.split(":")
    if len(parts) != 2 or not parts[0].isdecimal() or not parts[1].isdecimal():
        return None
    return parts[0], parts[1]


def is_canonical_ayah_key(ayah_key: str, surah_number: int) -> bool:
    """True when the key is the canonical "{surah}:{ayah}" decimal form (no leading zeros, ayah >= 1)."""
    parts = _split_ayah_key(ayah_key)
    if parts is None:
        return False
    ayah_number = int(parts[1])
    return parts[0] == str(surah_number) and parts[1] == str(ayah_number) and ayah_number >= 1


def timing_eligibility_reason(
    ayah_key: str, start_ms: int, end_ms: int, surah_number: int, track_duration_ms: int
) -> str | None:
    """
    Return why the slicer would reject this timing, or None when it is eligible.

    Single source of truth for the ayah-timing eligibility contract, shared by
    the slicer (which raises on rejection) and the storage sizing estimator
    (which excludes ineligible rows from its estimate and reports them
    separately). Eligibility is exactly: canonical "{surah}:{ayah}" key,
    start_ms >= 0, end_ms > start_ms and end_ms <= track.duration_ms.
    """
    if not is_canonical_ayah_key(ayah_key, surah_number):
        return "invalid or non-canonical ayah key"
    if start_ms < 0:
        return "start_ms must not be negative"
    if end_ms <= start_ms:
        return "end_ms must be greater than start_ms"
    if end_ms > track_duration_ms:
        return "end_ms must not exceed the track duration"
    return None


class RecitationAudioSlicingService:
    """
    Slice a surah MP3 track into one audio file per ayah using its ayah timings.

    Validation is all-or-nothing: every timing is checked before any download,
    ffmpeg run or upload, so invalid input never touches storage. Runtime
    failures are not rolled back - a failure partway through the loop leaves the
    already-written ayah objects in place. Those objects are deterministic
    (asset/folder/surah/ayah), so re-running the track overwrites them in place
    and converges to the full set; partial slices never accumulate.
    """

    def _get_s3_client(self):
        return boto3.client(
            "s3",
            endpoint_url=settings.CLOUDFLARE_R2_ENDPOINT,
            aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def _to_r2_key(self, key: str) -> str:
        """R2 object keys must be prefixed with "media/" to work with our bucket configuration."""
        _MEDIA_PREFIX = "media/"
        return key if key.startswith(_MEDIA_PREFIX) else f"{_MEDIA_PREFIX}{key}"

    def _build_slice_key(self, asset_id: int, folder_id: int, surah_number: int, ayah_number: int) -> str:
        """
        Deterministic storage key for one sliced ayah.

        Mirrors the track key grammar (uploads/assets/{asset_id}/recitations/...)
        used by ``upload_to_recitation_surah_track_files`` and the direct-upload
        service's ``_build_key``: the folder segment keeps variants (clear, echo)
        from overwriting each other, and the per-surah directory plus ayah leaf
        keeps slices from colliding with the track file itself.
        """
        return f"uploads/assets/{asset_id}/recitations/{folder_id}/{surah_number:03}/ayah_{ayah_number:03}.mp3"

    def slice_track(self, track_id: int) -> dict[str, Any]:
        """Slice every ayah of one track; returns track/asset ids, sliced count and generated keys."""
        try:
            track = RecitationSurahTrack.objects.get(pk=track_id)
        except RecitationSurahTrack.DoesNotExist as exc:
            raise ItqanError(
                error_name="track_not_found",
                message=_("Recitation track {track_id} not found.").format(track_id=track_id),
                status_code=404,
            ) from exc

        timings = list(track.ayah_timings.all().order_by("start_ms"))
        if not timings:
            return {"track_id": track.id, "asset_id": track.asset_id, "sliced": 0, "keys": []}

        self._validate_timings(track, timings)

        s3 = self._get_s3_client()
        keys: list[str] = []
        temp_dir = Path(tempfile.mkdtemp(prefix="ayah-slicing-"))
        try:
            source_path = temp_dir / "source.mp3"
            try:
                body = s3.get_object(Bucket=settings.CLOUDFLARE_R2_BUCKET, Key=self._to_r2_key(track.audio_file.name))[
                    "Body"
                ]
                try:
                    with open(source_path, "wb") as f:
                        shutil.copyfileobj(body, f)
                finally:
                    # Close always runs, but a cleanup failure must not mask a copy
                    # failure nor fail an otherwise-successful download.
                    try:
                        body.close()
                    except Exception:
                        logger.warning(
                            "Failed to close source audio stream for track %s",
                            track.id,
                            exc_info=True,
                        )
            except (ClientError, BotoCoreError) as exc:
                logger.warning("Failed to read source audio from storage for track %s", track.id, exc_info=True)
                raise ItqanError(
                    error_name="storage_error",
                    message=_("Failed to read source audio from storage for track {track_id}.").format(
                        track_id=track.id
                    ),
                    status_code=503,
                ) from exc

            audio_params = self._probe_audio_params(source_path)

            for timing in timings:
                ayah_number = self._parse_ayah_number(timing.ayah_key, track.surah_number)
                key = self._build_slice_key(track.asset_id, track.folder_id, track.surah_number, ayah_number)
                output_path = temp_dir / f"{track.surah_number:03}_{ayah_number:03}.mp3"
                self._run_ffmpeg(source_path, output_path, timing.start_ms, timing.end_ms, audio_params)
                try:
                    with open(output_path, "rb") as f:
                        s3.put_object(
                            Bucket=settings.CLOUDFLARE_R2_BUCKET,
                            Key=self._to_r2_key(key),
                            Body=f,
                            ContentType="audio/mpeg",
                        )
                except (ClientError, BotoCoreError) as exc:
                    logger.warning("Failed to store sliced ayah audio for track %s", track.id, exc_info=True)
                    raise ItqanError(
                        error_name="storage_error",
                        message=_("Failed to store sliced ayah audio for track {track_id}.").format(track_id=track.id),
                        status_code=503,
                    ) from exc
                keys.append(key)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        logger.info(f"Recitation track sliced [track_id={track.id}, asset_id={track.asset_id}, sliced={len(keys)}]")
        return {"track_id": track.id, "asset_id": track.asset_id, "sliced": len(keys), "keys": keys}

    def _validate_timings(self, track: RecitationSurahTrack, timings: list[RecitationAyahTiming]) -> None:
        """Reject the whole track when any ayah timing is invalid, before any slicing."""
        for timing in timings:
            self._parse_ayah_number(timing.ayah_key, track.surah_number)
            reason = timing_eligibility_reason(
                timing.ayah_key, timing.start_ms, timing.end_ms, track.surah_number, track.duration_ms
            )
            if reason is not None:
                self._raise_invalid_timing(track, timing, reason)

    @staticmethod
    def _raise_invalid_timing(track: RecitationSurahTrack, timing: RecitationAyahTiming, reason: str) -> None:
        raise ItqanError(
            error_name="invalid_ayah_timing",
            message=_("Track {track_id} has invalid ayah timing for {ayah_key}: {reason}").format(
                track_id=track.id, ayah_key=timing.ayah_key, reason=reason
            ),
            status_code=400,
        )

    @staticmethod
    def _parse_ayah_number(ayah_key: str, surah_number: int) -> int:
        """Parse a canonical "surah:ayah" key and return the ayah number; reject malformed keys."""
        parts = _split_ayah_key(ayah_key)
        if parts is None:
            raise ItqanError(
                error_name="invalid_ayah_timing",
                message=_('Ayah key {ayah_key} has an invalid format; expected "surah:ayah" using decimal digits.').format(
                    ayah_key=ayah_key
                ),
                status_code=400,
            )
        ayah_number = int(parts[1])
        # Canonical form is "{surah}:{ayah}" in plain decimal digits: no leading
        # zeros, so "1:1" and "1:01" can never alias the same slice key silently.
        if parts[0] != str(surah_number) or parts[1] != str(ayah_number) or ayah_number < 1:
            raise ItqanError(
                error_name="invalid_ayah_timing",
                message=_('Ayah key {ayah_key} must be canonical "{surah}:{ayah}" with no leading zeros.').format(
                    ayah_key=ayah_key, surah=surah_number, ayah=ayah_number
                ),
                status_code=400,
            )
        return ayah_number

    def _probe_audio_params(self, source_path: Path) -> dict[str, int | None]:
        """
        Read source MP3 audio parameters with mutagen for output fidelity.

        Only plain integers that are reliably available from MP3 metadata are
        returned (bitrate in bits/second, sample rate in Hz, channel count).
        Any failure - unreadable file, missing attribute, unexpected type -
        yields None for the affected property so slicing never depends on a
        probe succeeding. Details are logged internally; users only ever see
        ffmpeg failures, never probe internals.
        """
        try:
            from mutagen.mp3 import MP3  # type: ignore[import-not-found]

            audio = MP3(source_path)
        except Exception:
            logger.warning("Failed to probe source audio metadata for %s", source_path, exc_info=True)
            return {"bitrate": None, "sample_rate": None, "channels": None}

        info = getattr(audio, "info", None)
        params: dict[str, int | None] = {}
        for name in ("bitrate", "sample_rate", "channels"):
            value = None
            if info is not None:
                try:
                    value = getattr(info, name, None)
                except Exception as exc:
                    logger.warning("Failed to read %s from source audio %s: %s", name, source_path, exc)
            params[name] = value if isinstance(value, int) and value > 0 else None
        return params

    def _run_ffmpeg(
        self, source_path: Path, output_path: Path, start_ms: int, end_ms: int, audio_params: dict[str, int | None]
    ) -> None:
        """Slice [start_ms, end_ms) out of the source MP3 and apply short boundary fades."""
        duration_s = (end_ms - start_ms) / 1000
        fade_out_start_s = max(duration_s - FADE_DURATION_SECONDS, FADE_DURATION_SECONDS)
        fade_filter = (
            f"afade=t=in:st=0:d={FADE_DURATION_SECONDS},"
            f"afade=t=out:st={fade_out_start_s:.3f}:d={FADE_DURATION_SECONDS}"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-ss",
            f"{start_ms / 1000:.3f}",
            "-to",
            f"{end_ms / 1000:.3f}",
            "-af",
            fade_filter,
            "-c:a",
            "libmp3lame",
        ]
        # Preserve the source MP3 characteristics through the re-encode where
        # they are known. mutagen reports bitrate in bits/second and ffmpeg's
        # -b:a accepts a plain bits-per-second integer, so no conversion is
        # needed; -ar and -ac take Hz and channel count directly. Unknown
        # properties are omitted, keeping libmp3lame defaults.
        if audio_params.get("bitrate"):
            cmd += ["-b:a", str(audio_params["bitrate"])]
        if audio_params.get("sample_rate"):
            cmd += ["-ar", str(audio_params["sample_rate"])]
        if audio_params.get("channels"):
            cmd += ["-ac", str(audio_params["channels"])]
        cmd.append(str(output_path))
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_SLICE_TIMEOUT_SECONDS)
        except FileNotFoundError as exc:
            raise ItqanError(
                error_name="slicing_failed",
                message=_("ffmpeg binary not found; audio slicing is unavailable."),
                status_code=503,
            ) from exc
        except subprocess.TimeoutExpired as exc:
            logger.error("ffmpeg timed out slicing %s", output_path, exc_info=True)
            raise ItqanError(
                error_name="slicing_failed",
                message=_("Slicing ayah audio timed out."),
                status_code=503,
            ) from exc
        if completed.returncode != 0:
            # Raw stderr is logged internally only; the user-facing message stays generic.
            logger.error("ffmpeg failed slicing %s: %s", output_path, (completed.stderr or "").strip())
            raise ItqanError(
                error_name="slicing_failed",
                message=_("Failed to slice ayah audio with ffmpeg."),
                status_code=503,
            )
