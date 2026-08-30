from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.content.models import RecitationFolder
from apps.core.ninja_utils.errors import ItqanError

if TYPE_CHECKING:
    from apps.content.models import Asset


def sorted_asset_folders(asset: Asset) -> list[RecitationFolder]:
    """
    An asset's folders, default first then alphabetically.

    Sorted in Python rather than with .order_by() so a prefetched
    ``recitation_folders`` cache is reused instead of triggering a fresh query per
    row -- the recitation list endpoints serialize this for every row on the page.
    """
    return sorted(asset.recitation_folders.all(), key=lambda f: (not f.is_default, f.name or ""))


def visible_asset_folders(asset: Asset) -> list[RecitationFolder]:
    """Public/tenant list shape: visible folders only, same sort as ``sorted_asset_folders``."""
    return sorted(
        (f for f in asset.recitation_folders.all() if f.is_visible),
        key=lambda f: (not f.is_default, f.name or ""),
    )


def find_folder_by_token(asset_id: int, token: str, *, require_visible: bool = False) -> RecitationFolder | None:
    """
    Resolve a user-supplied ``?folder=`` value, which may be a slug **or** a folder name.

    Slug is tried first: it is unique per asset and is the canonical identifier we
    document and return in API responses. Failing that, the name is matched
    case-insensitively against the unlocalized column and both localized ones, so
    ``?folder=With%20echo`` and ``?folder=مع%20صدى`` both resolve.

    Names are not unique per asset -- two folders both called "Clear" get slugs
    ``clear`` and ``clear-1`` -- so a name matching several folders resolves to the
    default one when present and otherwise the oldest. That is deterministic rather
    than arbitrary; callers wanting an exact target should pass the slug.

    When ``require_visible`` is True (public/tenant reads), hidden folders resolve as
    not found so callers can raise ``folder_not_found``.

    Returns None when nothing matches, so the caller can raise ``folder_not_found``.
    """
    by_slug = RecitationFolder.objects.filter(asset_id=asset_id, slug=token).first()
    if by_slug is not None:
        if require_visible and not by_slug.is_visible:
            return None
        return by_slug

    matched = (
        RecitationFolder.objects.filter(asset_id=asset_id)
        .filter(Q(name__iexact=token) | Q(name_ar__iexact=token) | Q(name_en__iexact=token))
        .order_by("-is_default", "id")
        .first()
    )
    if matched is not None and require_visible and not matched.is_visible:
        return None
    return matched


def resolve_folder_for_asset(asset_id: int, folder_id: int | None) -> RecitationFolder:
    """
    Resolve which folder (variant) a write targets, defaulting to the asset's default.

    An explicit ``folder_id`` must belong to this asset, so a caller cannot write
    tracks or timings into another recitation's variant. Shared by the audio upload
    and ayah-timing upload paths, which must agree on this rule.
    """
    if folder_id is not None:
        folder = RecitationFolder.objects.filter(id=folder_id, asset_id=asset_id).first()
        if folder is None:
            raise ItqanError(
                error_name="folder_not_found",
                message=_("Folder {folder_id} does not belong to asset {asset_id}.").format(
                    folder_id=folder_id, asset_id=asset_id
                ),
                status_code=404,
            )
        return folder

    default_folder = RecitationFolder.objects.filter(asset_id=asset_id, is_default=True).first()
    if default_folder is None:
        raise ItqanError(
            error_name="folder_not_found",
            message=_("This recitation has no default folder."),
            status_code=404,
        )
    return default_folder
