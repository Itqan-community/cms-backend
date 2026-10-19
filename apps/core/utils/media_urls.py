from urllib.parse import quote

from django.conf import settings
from django.db.models.fields.files import FieldFile
from django.http import HttpRequest


def public_media_url(file: FieldFile, request: HttpRequest) -> str:
    """URL for a file anyone may fetch: the storage custom domain on R2, so Cloudflare caches
    and logs (counts) every request. Never use for restricted assets; their `file.url` is a
    signed, expiring link."""
    if settings.CLOUDFLARE_R2_ENDPOINT and settings.CLOUDFLARE_R2_PUBLIC_BASE_URL:
        return f"{settings.CLOUDFLARE_R2_PUBLIC_BASE_URL.rstrip('/')}/media/{quote(file.name)}"
    return request.build_absolute_uri(file.url)
