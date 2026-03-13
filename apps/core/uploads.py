import uuid
from typing import TYPE_CHECKING

from django.utils.text import slugify

if TYPE_CHECKING:
    from apps.content.models import (
        Asset,
        AssetPreview,
        AssetVersion,
        RecitationSurahTrack,
        Reciter,
        ResourceVersion,
    )
    from apps.publishers.models import Publisher


def _require_fk(instance: object, field: str, model_name: str, message: str) -> None:
    """Validate that a required foreign key field is not None or empty before generating an upload path."""
    value = getattr(instance, field, None)
    if value is None or value == "":
        raise ValueError(f"Cannot generate upload path: {model_name}.{field} is None. {message}")


def _safe_pk(instance: object) -> str:
    """Return the instance PK, or a UUID fallback for unsaved objects with AutoField PKs."""
    pk = getattr(instance, "id", None)
    if pk is None:
        return uuid.uuid4().hex[:8]
    return str(pk)


def upload_to_publisher_icons(instance: "Publisher", filename: str) -> str:
    """
    Generate upload path for publisher icon images
    Format: uploads/publishers/{publisher_id}/icon.{ext}
    """
    ext = filename.split(".")[-1].lower()
    filename = f"icon.{ext}"
    return f"uploads/publishers/{_safe_pk(instance)}/{filename}"


def upload_to_asset_thumbnails(instance: "Asset", filename: str) -> str:
    """
    Generate upload path for asset thumbnail images
    Format: uploads/assets/{asset_id}/thumbnail.{ext}
    """
    ext = filename.split(".")[-1].lower()
    filename = f"thumbnail.{ext}"
    return f"uploads/assets/{_safe_pk(instance)}/{filename}"


def upload_to_asset_preview_images(instance: "AssetPreview", filename: str) -> str:
    """
    Generate upload path for asset preview images
    Format: uploads/assets/{asset_id}/preview/{filename}
    """
    _require_fk(instance, "asset_id", "AssetPreview", "Link it to an Asset before uploading files.")
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    return f"uploads/assets/{instance.asset_id}/preview/{safe_filename}"


def upload_to_asset_files(instance: "AssetVersion", filename: str) -> str:
    """
    Generate upload path for asset version files
    Format: uploads/assets/{asset_id}/versions/{version_id}/{filename}
    """
    _require_fk(instance, "asset_id", "AssetVersion", "Link it to an Asset before uploading files.")
    # Keep original filename for downloadable assets
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    return f"uploads/assets/{instance.asset_id}/versions/{_safe_pk(instance)}/{safe_filename}"


def upload_to_resource_files(instance: "ResourceVersion", filename: str) -> str:
    """
    Generate upload path for resource version files
    Format: uploads/resources/{resource_id}/versions/{version_id}/{filename}
    """
    _require_fk(instance, "resource_id", "ResourceVersion", "Link it to a Resource before uploading files.")
    # Keep original filename for downloadable resources
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    return f"uploads/resources/{instance.resource_id}/versions/{_safe_pk(instance)}/{safe_filename}"


def upload_to_recitation_surah_track_files(instance: "RecitationSurahTrack", filename: str) -> str:
    """
    Generate upload path for recitation surah track audio files.
    Format: uploads/assets/{asset_id}/recitations/{surah_number:03}.{ext}
    """
    _require_fk(instance, "asset_id", "RecitationSurahTrack", "Link it to an Asset before uploading files.")
    if instance.surah_number is None:
        raise ValueError("Cannot generate upload path: RecitationSurahTrack.surah_number is None.")
    ext = filename.split(".")[-1].lower() if "." in filename else "mp3"
    return f"uploads/assets/{instance.asset_id}/recitations/{int(instance.surah_number):03}.{ext}"


def upload_to_reciter_image(instance: "Reciter", filename: str) -> str:
    """
    Generate upload path for reciter images
    Format: uploads/reciters/{reciter_id}/icon.{ext}
    """
    ext = filename.split(".")[-1].lower()
    filename = f"icon.{ext}"
    return f"uploads/reciters/{_safe_pk(instance)}/{filename}"
