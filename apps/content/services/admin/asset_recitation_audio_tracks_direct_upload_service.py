from __future__ import annotations

from io import BytesIO
from typing import Any

import boto3
from botocore.config import Config
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from apps.content.models import RecitationSurahTrack
from apps.core.ninja_utils.errors import ItqanError
from apps.mixins.recitations_helpers import (
    extract_surah_number_from_mp3_filename,
    get_mp3_duration_ms,
)


class AssetRecitationAudioTracksDirectUploadService:
    _MEDIA_PREFIX = "media/"

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
        """Convert DB/storage name (uploads/...) to actual R2 object key (media/uploads/...)."""
        return key if key.startswith(self._MEDIA_PREFIX) else f"{self._MEDIA_PREFIX}{key}"

    def _to_db_key(self, key: str) -> str:
        """Convert R2 object key (media/uploads/...) to DB/storage name (uploads/...) without media prefix for backward compatibility and to match default Django upload behavior"""
        return key[len(self._MEDIA_PREFIX) :] if key.startswith(self._MEDIA_PREFIX) else key

    def start_upload(self, asset_id: int, filename: str, duration_ms: int | None = None) -> dict[str, Any]:
        s3 = self._get_s3_client()
        surah_number = extract_surah_number_from_mp3_filename(filename)
        key = self._build_key(asset_id, surah_number)  # DB/storage name (no "media/" prefix)
        r2_key = self._to_r2_key(key)

        resp = s3.create_multipart_upload(
            Bucket=settings.CLOUDFLARE_R2_BUCKET,
            Key=r2_key,
            ContentType="audio/mpeg",
        )
        upload_id = resp["UploadId"]

        try:
            RecitationSurahTrack.objects.create(
                asset_id=asset_id,
                surah_number=surah_number,
                audio_file=key,
                original_filename=filename,
                duration_ms=duration_ms or 0,
                upload_finished_at=None,
            )
        except IntegrityError as err:
            # Prevent orphaned multipart uploads if the DB row already exists.
            s3.abort_multipart_upload(
                Bucket=settings.CLOUDFLARE_R2_BUCKET,
                Key=r2_key,
                UploadId=upload_id,
            )

            raise ItqanError(
                "duplicate_track",
                f"Track already exists for asset {asset_id} and surah {surah_number}",
                status_code=400,
            ) from err

        return {"key": key, "uploadId": upload_id, "contentType": "audio/mpeg", "surahNumber": surah_number}

    def sign_part(self, key: str, upload_id: str, part_number: int, expires_in: int = 3600) -> str:
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
        return url

    def finish_upload(self, key: str, upload_id: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
        s3 = self._get_s3_client()
        r2_key = self._to_r2_key(key)

        s3.complete_multipart_upload(
            Bucket=settings.CLOUDFLARE_R2_BUCKET,
            Key=r2_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": [{"ETag": p["ETag"], "PartNumber": int(p["PartNumber"])} for p in parts]},
        )

        # Compute size_bytes from the uploaded object
        try:
            head = s3.head_object(Bucket=settings.CLOUDFLARE_R2_BUCKET, Key=r2_key)
            size_bytes = int(head.get("ContentLength", 0))
        except Exception:
            size_bytes = 0

        # Get current track to check if duration_ms was already set
        track = RecitationSurahTrack.objects.only("duration_ms").get(audio_file=key)

        # Only compute duration_ms using mutagen as fallback if not already set
        duration_ms = track.duration_ms
        if not duration_ms or duration_ms == 0:
            try:
                obj = s3.get_object(Bucket=settings.CLOUDFLARE_R2_BUCKET, Key=r2_key)
                data = obj["Body"].read()
                duration_ms = get_mp3_duration_ms(BytesIO(data))
            except Exception:
                duration_ms = 0

        RecitationSurahTrack.objects.filter(audio_file=key).update(
            size_bytes=size_bytes,
            duration_ms=duration_ms,
            upload_finished_at=timezone.now(),
        )
        track = RecitationSurahTrack.objects.only(
            "id", "asset_id", "surah_number", "size_bytes", "upload_finished_at"
        ).get(audio_file=key)
        return {
            "trackId": track.id,
            "assetId": track.asset_id,
            "surahNumber": track.surah_number,
            "sizeBytes": track.size_bytes,
            "finishedAt": track.upload_finished_at.isoformat(),
            "key": key,
        }

    def abort_upload(self, key: str, upload_id: str) -> dict[str, Any]:
        """Abort a multipart upload and cleanup incomplete database record"""
        s3 = self._get_s3_client()
        r2_key = self._to_r2_key(key)
        db_key = self._to_db_key(key)

        # Abort the multipart upload in R2 (idempotent - ignore if not found)
        try:
            s3.abort_multipart_upload(
                Bucket=settings.CLOUDFLARE_R2_BUCKET,
                Key=r2_key,
                UploadId=upload_id,
            )
        except Exception as e:
            # If upload doesn't exist or already completed, that's fine
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code not in ("NoSuchUpload", "NotFound"):
                # Re-raise unexpected errors
                raise

        # Delete the incomplete database record (only if upload not finished)
        deleted_count = RecitationSurahTrack.objects.filter(
            audio_file=db_key,
            upload_finished_at__isnull=True,
        ).delete()[0]

        return {
            "key": db_key,
            "uploadId": upload_id,
            "aborted": True,
            "dbRecordsDeleted": deleted_count,
        }

    def cleanup_stuck_uploads(self, older_than_hours: int = 2) -> dict[str, Any]:
        """Find and abort multipart uploads that are stuck (older than threshold)"""
        from datetime import timedelta

        s3 = self._get_s3_client()
        cutoff_time = timezone.now() - timedelta(hours=older_than_hours)

        aborted_count = 0
        db_cleaned_count = 0
        errors = []

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
                        result = self.abort_upload(key=key, upload_id=upload_id)
                        aborted_count += 1
                        db_cleaned_count += result.get("dbRecordsDeleted", 0)
                    except Exception as e:
                        errors.append(f"Failed to abort {key}: {str(e)}")

        except Exception as e:
            errors.append(f"Cleanup failed: {str(e)}")

        return {
            "abortedUploads": aborted_count,
            "dbRecordsCleaned": db_cleaned_count,
            "errors": errors,
            "cutoffTime": cutoff_time.isoformat(),
        }
