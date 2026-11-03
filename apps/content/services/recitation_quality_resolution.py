from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Q
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.content.models import RecitationQuality
from apps.core.ninja_utils.errors import ItqanError

if TYPE_CHECKING:
    from apps.content.models import Asset


def reject_renamed_folder_param(request: HttpRequest) -> None:
    """``?folder=`` was renamed to ``?quality=``. Refuse it instead of ignoring it, so an old
    client gets an error rather than silently being served the default quality."""
    if "folder" in request.GET:
        raise ItqanError(
            error_name="folder_param_renamed",
            message=_("The folder parameter was renamed to quality. Use ?quality= instead."),
            status_code=400,
        )


def sorted_asset_qualities(asset: Asset) -> list[RecitationQuality]:
    """
    An asset's qualities, default first then alphabetically.

    Sorted in Python rather than with .order_by() so a prefetched
    ``recitation_qualities`` cache is reused instead of triggering a fresh query per
    row -- the recitation list endpoints serialize this for every row on the page.
    """
    return sorted(asset.recitation_qualities.all(), key=lambda f: (not f.is_default, f.name or ""))


def visible_asset_qualities(asset: Asset) -> list[RecitationQuality]:
    """Public/tenant list shape: visible qualities only, same sort as ``sorted_asset_qualities``."""
    return sorted(
        (f for f in asset.recitation_qualities.all() if f.is_visible),
        key=lambda f: (not f.is_default, f.name or ""),
    )


def find_quality_by_token(asset_id: int, token: str, *, require_visible: bool = False) -> RecitationQuality | None:
    """
    Resolve a user-supplied ``?quality=`` value, which may be a slug **or** a quality name.

    Slug is tried first: it is unique per asset and is the canonical identifier we
    document and return in API responses. Failing that, the name is matched
    case-insensitively against the unlocalized column and both localized ones, so
    ``?quality=With%20echo`` and ``?quality=مع%20صدى`` both resolve.

    Names are not unique per asset -- two qualities both called "Clear" get slugs
    ``clear`` and ``clear-1`` -- so a name matching several qualities resolves to the
    default one when present and otherwise the oldest. That is deterministic rather
    than arbitrary; callers wanting an exact target should pass the slug.

    When ``require_visible`` is True (public/tenant reads), hidden qualities resolve as
    not found so callers can raise ``quality_not_found``.

    Returns None when nothing matches, so the caller can raise ``quality_not_found``.
    """
    by_slug = RecitationQuality.objects.filter(asset_id=asset_id, slug=token).first()
    if by_slug is not None:
        if require_visible and not by_slug.is_visible:
            return None
        return by_slug

    matched = (
        RecitationQuality.objects.filter(asset_id=asset_id)
        .filter(Q(name__iexact=token) | Q(name_ar__iexact=token) | Q(name_en__iexact=token))
        .order_by("-is_default", "id")
        .first()
    )
    if matched is not None and require_visible and not matched.is_visible:
        return None
    return matched


def resolve_quality_for_asset(asset_id: int, quality_id: int | None) -> RecitationQuality:
    """
    Resolve which quality (variant) a write targets, defaulting to the asset's default.

    An explicit ``quality_id`` must belong to this asset, so a caller cannot write
    tracks or timings into another recitation's variant. Shared by the audio upload
    and ayah-timing upload paths, which must agree on this rule.
    """
    if quality_id is not None:
        quality = RecitationQuality.objects.filter(id=quality_id, asset_id=asset_id).first()
        if quality is None:
            raise ItqanError(
                error_name="quality_not_found",
                message=_("Quality {quality_id} does not belong to asset {asset_id}.").format(
                    quality_id=quality_id, asset_id=asset_id
                ),
                status_code=404,
            )
        return quality

    default_quality = RecitationQuality.objects.filter(asset_id=asset_id, is_default=True).first()
    if default_quality is None:
        raise ItqanError(
            error_name="quality_not_found",
            message=_("This recitation has no default quality."),
            status_code=404,
        )
    return default_quality
