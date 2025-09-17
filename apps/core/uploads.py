
from django.utils.text import slugify
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.publishers.models import Publisher


def upload_to_publisher_icons(instance:"Publisher", filename):
    """
    Generate upload path for publisher icon images
    Format: uploads/publishers/{slug}/icon.{ext}
    """
    ext = filename.split('.')[-1].lower()
    filename = f"icon.{ext}"
    return f"uploads/publishers/{instance.slug}/{filename}"


def upload_to_asset_thumbnails(instance, filename):
    """
    Generate upload path for asset thumbnail images
    Format: uploads/assets/{asset_id}/thumbnail.{ext}
    """
    ext = filename.split('.')[-1].lower()
    filename = f"thumbnail.{ext}"
    return f"uploads/assets/{instance.id}/{filename}"


def upload_to_asset_preview_images(instance, filename):
    """
    Generate upload path for asset snapshot images
    Format: uploads/assets/{asset_id}/snapshots/{filename}
    """
    safe_filename = slugify(filename.rsplit('.', 1)[0]) + '.' + filename.split('.')[-1].lower()
    asset_id = getattr(instance, 'asset_id', None) or getattr(instance, 'asset', None) or 'unknown'
    try:
        asset_id = asset_id if isinstance(asset_id, int) else asset_id.id
    except Exception:
        asset_id = 'unknown'
    return f"uploads/assets/{asset_id}/snapshots/{safe_filename}"




def upload_to_asset_files(instance, filename):
    """
    Generate upload path for asset version files
    Format: uploads/assets/{asset_id}/versions/{version_id}/{filename}
    """
    # Keep original filename for downloadable assets
    safe_filename = slugify(filename.rsplit('.', 1)[0]) + '.' + filename.split('.')[-1].lower()
    return f"uploads/assets/{instance.asset.id}/versions/{instance.id}/{safe_filename}"


def upload_to_resource_files(instance, filename):
    """
    Generate upload path for resource version files
    Format: uploads/resources/{resource_id}/versions/{semvar}/{filename}
    """
    # Keep original filename for downloadable resources
    safe_filename = slugify(filename.rsplit('.', 1)[0]) + '.' + filename.split('.')[-1].lower()
    safe_semvar = slugify(instance.semvar)
    return f"uploads/resources/{instance.resource.id}/versions/{safe_semvar}/{safe_filename}"
