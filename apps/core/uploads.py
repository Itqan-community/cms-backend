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


def _safe_own_id(instance_id: int | None) -> str:
    """Return the instance's own ID as a string, or a UUID fallback if unsaved.

    Only use for the instance's own primary key - never for foreign key
    references to parent objects, which should always be saved first.
    """
    if instance_id is None:
        return str(uuid.uuid4().hex[:12])
    return str(instance_id)


def _require_parent_id(parent_id: int | None, parent_name: str) -> str:
    """Return the parent ID as a string, raising ValueError if None.

    Parent objects must be saved before creating child upload paths.
    """
    if parent_id is None:
        raise ValueError(f"{parent_name} must be saved before uploading files.")
    return str(parent_id)


def upload_to_publisher_icons(instance: "Publisher", filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    filename = f"icon.{ext}"
    return f"uploads/publishers/{_safe_own_id(instance.id)}/{filename}"


def upload_to_asset_thumbnails(instance: "Asset", filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    filename = f"thumbnail.{ext}"
    return f"uploads/assets/{_safe_own_id(instance.id)}/{filename}"


def upload_to_asset_preview_images(instance: "AssetPreview", filename: str) -> str:
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    asset_id = _require_parent_id(instance.asset_id, "Asset")
    return f"uploads/assets/{asset_id}/preview/{safe_filename}"


def upload_to_asset_files(instance: "AssetVersion", filename: str) -> str:
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    asset_id = _require_parent_id(instance.asset_id, "Asset")
    return f"uploads/assets/{asset_id}/versions/{_safe_own_id(instance.id)}/{safe_filename}"


def upload_to_resource_files(instance: "ResourceVersion", filename: str) -> str:
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    resource_id = _require_parent_id(instance.resource_id, "Resource")
    return f"uploads/resources/{resource_id}/versions/{_safe_own_id(instance.id)}/{safe_filename}"


def upload_to_recitation_surah_track_files(instance: "RecitationSurahTrack", filename: str) -> str:
    ext = filename.split(".")[-1].lower() if "." in filename else "mp3"
    asset_id = _require_parent_id(instance.asset_id, "Asset")
    return f"uploads/assets/{asset_id}/recitations/{int(instance.surah_number):03}.{ext}"


def upload_to_reciter_image(instance: "Reciter", filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    filename = f"icon.{ext}"
    return f"uploads/reciters/{_safe_own_id(instance.id)}/{filename}"
