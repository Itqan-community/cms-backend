from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
import os

import boto3
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class DeleteFilesOnDeleteMixin:
    """
    Mixin to ensure any FileField/ImageField files are deleted from storage
    when the model instance is deleted.

    Attach to any model that has FileField/ImageField. Works with bulk deletes
    as we hook into post_delete and iterate the instance's file fields.
    """

    @classmethod
    def _iter_file_fields(cls) -> Iterable[models.Field]:
        for field in cls._meta.get_fields():  # type: ignore[attr-defined]
            if isinstance(field, (models.FileField | models.ImageField)):
                yield field


@receiver(post_delete)
def delete_associated_files_on_delete(sender, instance, **kwargs):
    """
    Global receiver: only acts for instances that subclass DeleteFilesOnDeleteMixin.
    Deletes all FileField/ImageField from storage without saving the model again.
    """
    if not isinstance(instance, DeleteFilesOnDeleteMixin):
        return
    try:
        for field in instance._iter_file_fields():  # type: ignore[attr-defined]
            try:
                f = getattr(instance, field.name, None)
                if f and getattr(f, "name", ""):
                    f.delete(save=False)
            except Exception:
                # Best-effort: ignore storage errors during cleanup
                pass
    except Exception:
        # Do not raise from signals
        pass


# ===========================
# Cloudflare R2 presign utils
# ===========================


@lru_cache(maxsize=1)
def _get_s3_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=settings.CLOUDFLARE_R2_ENDPOINT,
        aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def generate_presigned_download_url(key: str, filename: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned GET URL for Cloudflare R2 with forced download.
    - key: object key within the bucket
    - filename: suggested filename for download (simple ascii acceptable)
    - expires_in: seconds until URL expiry
    """
    filename = os.path.basename(filename) if filename else "download"
    params = {
        "Bucket": settings.CLOUDFLARE_R2_BUCKET,
        "Key": key,
        "ResponseContentDisposition": f'attachment; filename="{filename}"',
    }
    return _get_s3_client().generate_presigned_url("get_object", Params=params, ExpiresIn=expires_in)
