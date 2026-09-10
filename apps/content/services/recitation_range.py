from __future__ import annotations

import hashlib
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

from apps.content.services.admin.recitation_audio_slicing_service import (
    FADE_DURATION_SECONDS,
    FFMPEG_SLICE_TIMEOUT_SECONDS,
)
from apps.core.ninja_utils.errors import ItqanError
from config.settings.base import CLOUDFLARE_R2_PUBLIC_BASE_URL

if TYPE_CHECKING:
    from apps.content.models import RecitationAyahTiming, RecitationFolder, RecitationSurahTrack

logger = logging.getLogger(__name__)

# Bump ONLY when the encoder/filter pipeline changes (e.g. the -ss/-t cut fix):
# it retires every clip cut by older code so persisted audio can never reflect
# a previous algorithm. Content changes (audio file, timing edits) rotate keys
# on their own via _source_version().
BUILD_VERSION = 2


class RecitationRangeService:
    """Build (or reuse) one combined MP3 for a contiguous ayah range in a surah track.

    The range is contiguous, so a single ffmpeg ``-ss start -t duration`` cut of
    the surah track covers it exactly (including small inter-ayah gaps); no
    N-way concat is needed. Fades apply only at the outer boundaries.
    Storage keys are deterministic per *content*: the leaf embeds a build-version
    token and a content hash (source audio object + every timing boundary), so
    any writer that changes clip bytes rotates the key instead of serving or
    overwriting a stale object.
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
        # R2 object keys must be prefixed with "media/" (same as the slicer).
        media_prefix = "media/"
        return key if key.startswith(media_prefix) else f"{media_prefix}{key}"

    def _prune_stale_range_clips(
        self,
        s3: Any,
        *,
        asset_id: int,
        folder_id: int,
        surah_number: int,
        from_ayah: int,
        to_ayah: int,
        current_key: str,
    ) -> None:
        # Delete same-range clips at older build/content versions, including the
        # pre-versioning unversioned format, so dead objects do not accumulate.
        # A single LIST per build is cheap because builds are rare; hits never
        # pay for it. Leaf tokens rotate, so pruning never races a valid hit on
        # a different version: a concurrent miss simply rebuilds its own key.
        bucket = settings.CLOUDFLARE_R2_BUCKET
        dir_key = self._to_r2_key(f"uploads/assets/{asset_id}/recitations/{folder_id}/{surah_number:03}")
        expected_leaf = f"range_{from_ayah:03}_{to_ayah:03}"
        current_full = self._to_r2_key(current_key)
        stale: list[str] = []
        continuation: str | None = None
        while True:
            params: dict[str, Any] = {"Bucket": bucket, "Prefix": f"{dir_key}/"}
            if continuation:
                params["ContinuationToken"] = continuation
            page = s3.list_objects_v2(**params)
            for obj in page.get("Contents", []) or []:
                full_key = obj["Key"]
                if full_key == current_full:
                    continue
                leaf = full_key.rsplit("/", 1)[-1]
                if leaf.startswith(expected_leaf) and leaf.endswith(".mp3"):
                    stale.append(full_key)
            if page.get("IsTruncated"):
                continuation = page.get("NextContinuationToken")
            else:
                break
        if stale:
            s3.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": k} for k in stale], "Quiet": True},
            )

    @staticmethod
    def _source_version(track: RecitationSurahTrack, subset: list[RecitationAyahTiming]) -> str:
        # Content-derived token covering exactly what determines the clip's
        # bytes: the source audio object + every timing boundary in the subset.
        # Whichever writer changes inputs (timing upload, direct audio upload,
        # track delete+recreate, raw SQL) rotates the token and thereby the
        # persisted key, so a stale clip can never be served. Audio is keyed by
        # its object name; byte-for-byte in-place overwrites under the same name
        # are not produced by any writer in this codebase and are the only case
        # left uncovered.
        # Non-security key derivation (blake2b, like apps/content/cache.py):
        # short digest keeps the persisted filename tidy.
        digest = hashlib.blake2b(digest_size=6)
        digest.update(f"{track.audio_file.name}\x00".encode())
        for timing in subset:
            digest.update(f"{timing.ayah_key}:{timing.start_ms}:{timing.end_ms}\x00".encode())
        return digest.hexdigest()

    def build_range_key(
        self,
        asset_id: int,
        folder_id: int,
        surah_number: int,
        from_ayah: int,
        to_ayah: int,
        version: str,
    ) -> str:
        # Deterministic key mirroring the slice grammar
        # (uploads/assets/{id}/recitations/...): folder segment keeps variants
        # apart, surah dir + range leaf never collides with the track file.
        # The leaf version token (build + content hash) rotates on any input
        # change so persisted clips can never go stale.
        return (
            f"uploads/assets/{asset_id}/recitations/{folder_id}/"
            f"{surah_number:03}/range_{from_ayah:03}_{to_ayah:03}_b{BUILD_VERSION}_{version}.mp3"
        )

    def range_exists(self, key: str) -> dict[str, Any] | None:
        # Return object metadata when the combined clip already exists, else None.
        if not settings.CLOUDFLARE_R2_BUCKET:
            return None
        try:
            head = self._get_s3_client().head_object(Bucket=settings.CLOUDFLARE_R2_BUCKET, Key=self._to_r2_key(key))
        except (ClientError, BotoCoreError):
            return None
        return head

    def get_or_build_range_audio(
        self,
        track: RecitationSurahTrack,
        folder: RecitationFolder,
        surah_number: int,
        from_ayah: int,
        to_ayah: int,
        start_ms: int,
        end_ms: int,
        subset: list[RecitationAyahTiming],
    ) -> dict[str, Any]:
        # Serve the persisted combined clip when present; otherwise cut it from
        # the surah track once, upload it, and return its URL + byte size. The
        # key embeds a content version, so an R2 hit is only ever served for the
        # exact audio+timing+encoder inputs that produced it.
        if not settings.CLOUDFLARE_R2_BUCKET:
            raise ItqanError(
                error_name="storage_error",
                message=_("Audio storage is not configured."),
                status_code=503,
            )
        version = self._source_version(track, subset)
        key = self.build_range_key(track.asset_id, folder.id, surah_number, from_ayah, to_ayah, version)
        existing = self.range_exists(key)
        if existing is not None:
            return {
                "key": key,
                "audio_url": f"{CLOUDFLARE_R2_PUBLIC_BASE_URL}/media/{key}",
                "duration_ms": end_ms - start_ms,
                "size_bytes": int(existing.get("ContentLength") or 0),
            }

        s3 = self._get_s3_client()
        temp_dir = Path(tempfile.mkdtemp(prefix="ayah-range-"))
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
                    try:
                        body.close()
                    except Exception:
                        logger.warning("Failed to close source audio stream for track %s", track.id, exc_info=True)
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
            output_path = temp_dir / f"range_{surah_number:03}_{from_ayah:03}_{to_ayah:03}.mp3"
            self._run_ffmpeg_cut(source_path, output_path, start_ms, end_ms, audio_params)
            size_bytes = output_path.stat().st_size
            try:
                with open(output_path, "rb") as f:
                    s3.put_object(
                        Bucket=settings.CLOUDFLARE_R2_BUCKET,
                        Key=self._to_r2_key(key),
                        Body=f,
                        ContentType="audio/mpeg",
                    )
            except (ClientError, BotoCoreError) as exc:
                logger.warning("Failed to store ayah-range audio for track %s", track.id, exc_info=True)
                raise ItqanError(
                    error_name="storage_error",
                    message=_("Failed to store ayah-range audio for track {track_id}.").format(track_id=track.id),
                    status_code=503,
                ) from exc
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Retire any same-range clip from an older content/build version so the
        # surah dir never accumulates dead objects. Runs only on a build (the
        # rare path); hits never LIST. Best-effort: cleanup failures must never
        # fail the request that just produced a valid clip.
        try:
            self._prune_stale_range_clips(
                s3,
                asset_id=track.asset_id,
                folder_id=folder.id,
                surah_number=surah_number,
                from_ayah=from_ayah,
                to_ayah=to_ayah,
                current_key=key,
            )
        except Exception:
            logger.warning("Failed to prune stale ayah-range clips for track %s", track.id, exc_info=True)

        logger.info(
            "Recitation range built [asset_id=%s, surah=%s, range=%s-%s]",
            track.asset_id,
            surah_number,
            from_ayah,
            to_ayah,
        )
        return {
            "key": key,
            "audio_url": f"{CLOUDFLARE_R2_PUBLIC_BASE_URL}/media/{key}",
            "duration_ms": end_ms - start_ms,
            "size_bytes": size_bytes,
        }

    def _probe_audio_params(self, source_path: Path) -> dict[str, int | None]:
        # Keep output fidelity by reusing the source bitrate/sample-rate/channels
        # when known; unknown properties fall back to libmp3lame defaults.
        try:
            from mutagen.mp3 import MP3  # type: ignore[import-not-found]

            audio = MP3(source_path)
        except Exception:
            logger.warning("Failed to probe source audio metadata for %s", source_path, exc_info=True)
            return {"bitrate": None, "sample_rate": None, "channels": None}
        info = getattr(audio, "info", None)
        params: dict[str, int | None] = {}
        for name in ("bitrate", "sample_rate", "channels"):
            value = getattr(info, name, None) if info is not None else None
            params[name] = value if isinstance(value, int) and value > 0 else None
        return params

    def _run_ffmpeg_cut(
        self, source_path: Path, output_path: Path, start_ms: int, end_ms: int, audio_params: dict[str, int | None]
    ) -> None:
        # Cut [start_ms, end_ms) with short fades only at the outer boundaries
        # (inner ayah joints stay untouched so memorization loops sound natural).
        # -ss goes BEFORE -i (input seeking): the output timestamps restart at 0
        # from the seek point, so -t (duration) then means the exact segment
        # length. Output seeking (-ss after -i) with -to=end would instead
        # produce stream length `end`, i.e. `start` seconds of trailing silence
        # after the fade-out.
        duration_s = (end_ms - start_ms) / 1000
        fade_duration_s = min(FADE_DURATION_SECONDS, duration_s / 2)
        fade_out_start_s = duration_s - fade_duration_s
        fade_filter = f"afade=t=in:st=0:d={fade_duration_s},afade=t=out:st={fade_out_start_s:.3f}:d={fade_duration_s}"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_ms / 1000:.3f}",
            "-i",
            str(source_path),
            "-t",
            f"{duration_s:.3f}",
            "-af",
            fade_filter,
            "-c:a",
            "libmp3lame",
        ]
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
            logger.error("ffmpeg timed out building ayah range %s", output_path, exc_info=True)
            raise ItqanError(
                error_name="slicing_failed",
                message=_("Building ayah-range audio timed out."),
                status_code=503,
            ) from exc
        if completed.returncode != 0:
            logger.error("ffmpeg failed building ayah range %s: %s", output_path, (completed.stderr or "").strip())
            raise ItqanError(
                error_name="slicing_failed",
                message=_("Failed to build ayah-range audio with ffmpeg."),
                status_code=503,
            )
