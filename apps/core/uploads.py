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


def upload_to_publisher_icons(instance: "Publisher", filename: str) -> str:
    """
    Generate upload path for publisher icon images
    Format: uploads/publishers/{publisher_id}/icon.{ext}
    """
    ext = filename.split(".")[-1].lower()
    filename = f"icon.{ext}"
    return f"uploads/publishers/{instance.id}/{filename}"


def upload_to_asset_thumbnails(instance: "Asset", filename: str) -> str:
    """
    Generate upload path for asset thumbnail images
    Format: uploads/assets/{asset_id}/thumbnail.{ext}
    """
    ext = filename.split(".")[-1].lower()
    filename = f"thumbnail.{ext}"
    return f"uploads/assets/{instance.id}/{filename}"


def upload_to_asset_preview_images(instance: "AssetPreview", filename: str) -> str:
    """
    Generate upload path for asset preview images
    Format: uploads/assets/{asset_id}/preview/{filename}
    """
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    return f"uploads/assets/{instance.asset_id}/preview/{safe_filename}"


def upload_to_asset_files(instance: "AssetVersion", filename: str) -> str:
    """
    Generate upload path for asset version files
    Format: uploads/assets/{asset_id}/versions/{asset_version_id}/{filename}
    """
    # Keep original filename for downloadable assets
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    version_id = instance.pk or f"tmp-{uuid.uuid4().hex[:8]}"
    return f"uploads/assets/{instance.asset_id}/versions/{version_id}/{safe_filename}"


def upload_to_resource_files(instance: "ResourceVersion", filename: str) -> str:
    """
    Generate upload path for resource version files
    Format: uploads/resources/{resource_id}/versions/{resource_version_id}/{filename}
    """
    # Keep original filename for downloadable resources
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    version_id = instance.pk or f"tmp-{uuid.uuid4().hex[:8]}"
    return f"uploads/resources/{instance.resource_id}/versions/{version_id}/{safe_filename}"


def upload_to_recitation_surah_track_files(instance: "RecitationSurahTrack", filename: str) -> str:
    """
    Generate upload path for recitation surah track audio files.
    Format: uploads/assets/{asset_id}/recitations/{surah_number:03}.{ext}
    """
    ext = filename.split(".")[-1].lower() if "." in filename else "mp3"
    return f"uploads/assets/{instance.asset_id}/recitations/{int(instance.surah_number):03}.{ext}"


def upload_to_reciter_image(instance: "Reciter", filename: str) -> str:
    """
    Generate upload path for publisher icon images
    Format: uploads/reciters/{reciter_id}/image.{ext}
    """
    ext = filename.split(".")[-1].lower()
    filename = f"icon.{ext}"
    return f"uploads/reciters/{instance.id}/{filename}"
