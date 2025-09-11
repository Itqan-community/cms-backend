from typing import TYPE_CHECKING

from django.utils.text import slugify

if TYPE_CHECKING:
    from apps.content.models import Publisher


def upload_organization_covers(instance, filename):
    """
    Generate upload path for organization cover images
    Format: uploads/organizations/{org_slug}/cover.{ext}
    """
    ext = filename.split(".")[-1].lower()
    filename = f"cover.{ext}"
    return f"uploads/organizations/{instance.slug}/{filename}"


def upload_asset_thumbnails(instance, filename):
    """
    Generate upload path for asset thumbnail images
    Format: uploads/assets/{asset_id}/thumbnail.{ext}
    """
    ext = filename.split(".")[-1].lower()
    filename = f"thumbnail.{ext}"
    return f"uploads/assets/{instance.id}/{filename}"


def upload_user_avatars(instance, filename):
    """
    Generate upload path for user avatar images
    Format: uploads/users/{user_id}/avatar.{ext}
    """
    ext = filename.split(".")[-1].lower()
    filename = f"avatar.{ext}"
    return f"uploads/users/{instance.id}/{filename}"


def upload_asset_files(instance, filename):
    """
    Generate upload path for asset version files
    Format: uploads/assets/{asset_id}/versions/{version_id}/{filename}
    """
    # Keep original filename for downloadable assets
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    return f"uploads/assets/{instance.asset.id}/versions/{instance.id}/{safe_filename}"


def upload_resource_files(instance, filename):
    """
    Generate upload path for resource version files
    Format: uploads/resources/{resource_id}/versions/{semvar}/{filename}
    """
    # Keep original filename for downloadable resources
    safe_filename = slugify(filename.rsplit(".", 1)[0]) + "." + filename.split(".")[-1].lower()
    safe_semvar = slugify(instance.semvar)
    return f"uploads/resources/{instance.resource.id}/versions/{safe_semvar}/{safe_filename}"


def upload_publisher_icon(instance: "Publisher", filename):
    """
    Generate upload path for organization icon images
    Format: uploads/organizations/{org_slug}/icon.{ext}
    """
    ext = filename.split(".")[-1].lower()
    filename = f"icon.{ext}"
    return f"uploads/organizations/{instance.slug}/{filename}"
