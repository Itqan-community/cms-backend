from typing import TYPE_CHECKING
import uuid

from apps.core.slugs import slugify_text

if TYPE_CHECKING:
    from apps.content.models import (
        Asset,
        AssetPreview,
        AssetVersion,
        RecitationAyahTiming,
        RecitationSurahTrack,
        Reciter,
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
    safe_filename = slugify_text(filename.rsplit(".", 1)[0], max_length=255) + "." + filename.split(".")[-1].lower()
    return f"uploads/assets/{instance.asset_id}/preview/{safe_filename}"


def upload_to_asset_files(instance: "AssetVersion", filename: str) -> str:
    """
    Generate upload path for asset version files
    Format: uploads/assets/{asset_id}/versions/{asset_version_id}/{filename}
    """
    # Keep original filename for downloadable assets
    safe_filename = slugify_text(filename.rsplit(".", 1)[0], max_length=255) + "." + filename.split(".")[-1].lower()
    version_id = instance.pk or f"tmp-{uuid.uuid4().hex[:8]}"
    return f"uploads/assets/{instance.asset_id}/versions/{version_id}/{safe_filename}"


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


def upload_to_recitation_ayah_audio(instance: "RecitationAyahTiming", filename: str) -> str:
    """
    Stable, deterministic storage key for one sliced per-ayah audio file.

    Format: uploads/assets/{asset_id}/recitations/{folder_id}/{surah_number:03}/ayah_{ayah_number:03}.mp3

    Mirrors RecitationAudioSlicingService._build_slice_key() exactly so the key
    written by the slicer is always identical to the key stored here. Never
    coupled to user input — asset_id, folder_id and surah_number come from the
    related RecitationSurahTrack; ayah_number is parsed from the canonical
    "{surah}:{ayah}" ayah_key field.
    """
    surah_number: int = instance.track.surah_number
    folder_id: int = instance.track.folder_id
    asset_id: int = instance.track.asset_id
    ayah_number: int = int(instance.ayah_key.split(":")[1])
    return f"uploads/assets/{asset_id}/recitations/{folder_id}/{surah_number:03}/ayah_{ayah_number:03}.mp3"
