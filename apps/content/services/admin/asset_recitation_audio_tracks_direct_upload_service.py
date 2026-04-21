from __future__ import annotations

from io import BytesIO
import logging
from typing import Any

import boto3
from botocore.config import Config
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.content.repositories.recitation_track import RecitationTrackRepository
from apps.core.ninja_utils.errors import ItqanError
from apps.mixins.recitations_helpers import extract_surah_number_from_mp3_filename, get_mp3_duration_ms

logger = logging.getLogger(__name__)


class AssetRecitationAudioTracksDirectUploadService:
    def _get_s3_client(self):
        return boto3.client(
            "s3",
            endpoint_url=settings.CLOUDFLARE_R2_ENDPOINT,
            aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def _build_key(self, asset_id: int, surah_number: int) -> str:
        return f"uploads/assets/{asset_id}/recitations/{surah_number:03}.mp3"

    def _to_r2_key(self, key: str) -> str:
        """R2 object keys must be prefixed with "media/" to work with our bucket configuration"""
        _MEDIA_PREFIX = "media/"
        return key if key.startswith(_MEDIA_PREFIX) else f"{_MEDIA_PREFIX}{key}"

    def start_upload(self, asset_id: int, filename: str) -> dict[str, Any]:
        s3 = self._get_s3_client()
        surah_number = extract_surah_number_from_mp3_filename(filename)

        key = self._build_key(asset_id, surah_number)  # DB/storage name (no "media/" prefix)
        r2_key = self._to_r2_key(key)  # R2 object key with "media/" prefix

        response = s3.create_multipart_upload(
            Bucket=settings.CLOUDFLARE_R2_BUCKET,
            Key=r2_key,
            ContentType="audio/mpeg",
        )
        upload_id = response["UploadId"]

        return {
            "key": key,
            "uploadId": upload_id,
            "contentType": "audio/mpeg",
            "surahNumber": surah_number,
            "assetId": asset_id,
            "filename": filename,
        }

    def sign_part(self, key: str, upload_id: str, part_number: int, expires_in: int = 3600) -> dict[str, Any]:
        s3 = self._get_s3_client()
        r2_key = self._to_r2_key(key)
        url = s3.generate_presigned_url(
            ClientMethod="upload_part",
            Params={
                "Bucket": settings.CLOUDFLARE_R2_BUCKET,
                "Key": r2_key,
                "UploadId": upload_id,
                "PartNumber": int(part_number),
            },
            ExpiresIn=expires_in,
            HttpMethod="PUT",
        )
        return {"url": url}

    def finish_upload(
        self,
        key: str,
        upload_id: str,
        parts: list[dict[str, Any]],
        asset_id: int,
        filename: str,
        duration_ms: int | None = None,
        size_bytes: int | None = None,
    ) -> dict[str, Any]:
        s3 = self._get_s3_client()
        r2_key = self._to_r2_key(key)

        s3.complete_multipart_upload(
            Bucket=settings.CLOUDFLARE_R2_BUCKET,
            Key=r2_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": [{"ETag": p["ETag"], "PartNumber": int(p["PartNumber"])} for p in parts]},
        )

        # Fall back to head_object if size_bytes not provided or 0
        if not size_bytes:
            try:
                logger.info("backend server are computing size_bytes instead of of parsing it directly from frontend!")
                head = s3.head_object(Bucket=settings.CLOUDFLARE_R2_BUCKET, Key=r2_key)
                size_bytes = int(head.get("ContentLength", 0))
            except Exception as e:
                logger.warning(f"Failed to get size for uploaded object {r2_key}: {e}")
                size_bytes = 0

        # Fall back to mutagen if duration_ms not provided or 0
        if not duration_ms:
            try:
                logger.info("backend server are computing duration_ms instead of parsing it directly from frontend!")
                obj = s3.get_object(Bucket=settings.CLOUDFLARE_R2_BUCKET, Key=r2_key)
                data = obj["Body"].read()
                duration_ms = get_mp3_duration_ms(BytesIO(data))
            except Exception as e:
                logger.warning(f"Failed to compute MP3 duration for {r2_key}: {e}")
                duration_ms = 0

        surah_number = extract_surah_number_from_mp3_filename(filename)

        repo = RecitationTrackRepository()
        try:
            with transaction.atomic():
                track = repo.create_recitation_track(
                    asset_id=asset_id,
                    surah_number=surah_number,
                    audio_file=key,
                    original_filename=filename,
                    duration_ms=duration_ms,
                    size_bytes=size_bytes,
                    upload_finished_at=timezone.now(),
                )
        except IntegrityError as exc:
            try:
                s3.delete_object(Bucket=settings.CLOUDFLARE_R2_BUCKET, Key=r2_key)
            except Exception as e:
                logger.warning(f"Failed to delete orphaned object in R2 {r2_key}: {e}")

            raise ItqanError(
                error_name="duplicate_track",
                message=f"A track for asset {asset_id} surah {surah_number} already exists",
                status_code=409,
            ) from exc

        logger.info(
            f"Multipart upload complete [asset_id={asset_id}, surah_number={surah_number}, track_id={track.id}, size_bytes={track.size_bytes}]"
        )
        return {
            "trackId": track.id,
            "assetId": track.asset_id,
            "surahNumber": track.surah_number,
            "sizeBytes": track.size_bytes,
            "finishedAt": track.upload_finished_at.isoformat(),
            "key": key,
        }

    def abort_upload(self, key: str, upload_id: str) -> dict[str, Any]:
        """Abort a multipart upload in R2."""
        s3 = self._get_s3_client()
        r2_key = self._to_r2_key(key)

        try:
            s3.abort_multipart_upload(
                Bucket=settings.CLOUDFLARE_R2_BUCKET,
                Key=r2_key,
                UploadId=upload_id,
            )
        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code not in ("NoSuchUpload", "NotFound"):
                raise
            logger.warning(f"Multipart upload abort skipped for {r2_key} (code={error_code}): {e}")

        return {"aborted": True}

    def cleanup_stuck_uploads(self, older_than_hours: int = 2) -> dict[str, Any]:
        """Find and abort stuck multipart uploads older than threshold"""
        from datetime import timedelta

        s3 = self._get_s3_client()
        cutoff_time = timezone.now() - timedelta(hours=older_than_hours)

        aborted_count = 0

        try:
            # List all incomplete multipart uploads under the prefix
            response = s3.list_multipart_uploads(
                Bucket=settings.CLOUDFLARE_R2_BUCKET,
                Prefix="media/uploads/assets/",
            )

            uploads = response.get("Uploads", [])

            for upload in uploads:
                initiated = upload.get("Initiated")
                if not initiated:
                    continue

                initiated_time = timezone.make_aware(initiated) if initiated.tzinfo is None else initiated

                if initiated_time < cutoff_time:
                    key = upload.get("Key")
                    upload_id = upload.get("UploadId")

                    try:
                        self.abort_upload(key=key, upload_id=upload_id)
                        aborted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to abort stuck upload {key}: {e}")

        except Exception as e:
            logger.error(f"Stuck upload cleanup failed: {e}")

        return {
            "abortedUploads": aborted_count,
            "cutoffTime": cutoff_time.isoformat(),
        }
