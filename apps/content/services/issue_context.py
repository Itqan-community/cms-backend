"""Where in an asset an issue report points: a typed ``context`` per asset category.

Each category that has a meaningful location gets its own schema:

- recitation and text assets: ``{"surah": 2, "ayah": 255}`` (both required)
- mushaf: ``{"page": 12}`` (required)
- font: ``{"page": 12}``, ``{"glyph": "ب"}`` or both (at least one required)

For these categories the context is mandatory. Every other category
(program, …) takes no context: ``None`` or ``{}``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.utils.translation import get_language, gettext as _
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, ValidationError

from apps.content.models import CategoryChoice
from apps.core.mixins.constants import QURAN_SURAHS
from apps.core.ninja_utils.errors import ItqanError

if TYPE_CHECKING:
    from apps.content.models import Asset

GLYPH_MAX_LENGTH = 32
# A page number with no known page count still has to fit the page columns (PositiveSmallIntegerField).
PAGE_MAX_WITHOUT_LAYOUT = 32767


class _ContextSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AyahContext(_ContextSchema):
    surah: StrictInt
    ayah: StrictInt


class PageContext(_ContextSchema):
    page: StrictInt


class FontContext(_ContextSchema):
    page: StrictInt | None = None
    glyph: StrictStr | None = None


CONTEXT_SCHEMAS: dict[str, type[_ContextSchema]] = {
    CategoryChoice.RECITATION: AyahContext,
    CategoryChoice.TEXT: AyahContext,
    CategoryChoice.MUSHAF: PageContext,
    CategoryChoice.FONT: FontContext,
}


def _invalid(message: str) -> ItqanError:
    return ItqanError(error_name="invalid_issue_context", message=message, status_code=400)


def _check_surah_ayah(context: AyahContext) -> None:
    surah = QURAN_SURAHS.get(context.surah)
    if surah is None:
        raise _invalid(_("Surah must be between 1 and 114."))
    if not 1 <= context.ayah <= surah["ayahs_count"]:
        raise _invalid(
            _("Ayah must be between 1 and {count} for surah {surah}.").format(
                count=surah["ayahs_count"], surah=context.surah
            )
        )


def _check_page(page: int, asset: Asset) -> None:
    page_count = asset.mushaf_layout.page_count if asset.mushaf_layout_id else PAGE_MAX_WITHOUT_LAYOUT
    if not 1 <= page <= page_count:
        raise _invalid(_("Page must be between 1 and {count}.").format(count=page_count))


def _check_required(category: str, context: dict[str, Any]) -> None:
    """Every category with a location needs its fields filled in, each with its own message."""
    if category in (CategoryChoice.RECITATION, CategoryChoice.TEXT):
        if "surah" not in context or "ayah" not in context:
            raise _invalid(_("Choose the surah and ayah."))
    elif category == CategoryChoice.MUSHAF:
        if "page" not in context:
            raise _invalid(_("Enter the page."))
    elif category == CategoryChoice.FONT:
        if "page" not in context and "glyph" not in context:
            raise _invalid(_("Enter the page or the glyph."))


def validate_issue_context(asset: Asset, context: dict[str, Any] | None) -> dict[str, Any] | None:
    """The cleaned context for a report on ``asset``; ``None`` for categories that take no location.

    Raises ``ItqanError("invalid_issue_context")`` when the context is missing,
    incomplete, or does not fit the asset's category.
    """
    if context is not None and not isinstance(context, dict):
        raise _invalid(_("The issue location must be an object."))
    # A cleared field (null / blank) is the same as a missing one.
    stripped = {key: value.strip() if isinstance(value, str) else value for key, value in (context or {}).items()}
    context = {key: value for key, value in stripped.items() if value is not None and value != ""}

    schema = CONTEXT_SCHEMAS.get(asset.category)
    if schema is None:
        if context:
            raise _invalid(_("This asset type does not take an issue location."))
        return None
    _check_required(asset.category, context)
    try:
        parsed = schema.model_validate(context)
    except ValidationError:
        raise _invalid(_("The issue location does not fit this asset type.")) from None

    if isinstance(parsed, AyahContext):
        _check_surah_ayah(parsed)
    elif isinstance(parsed, PageContext):
        _check_page(parsed.page, asset)
    elif isinstance(parsed, FontContext):
        if parsed.page is not None:
            _check_page(parsed.page, asset)
        if parsed.glyph is not None and len(parsed.glyph) > GLYPH_MAX_LENGTH:
            raise _invalid(_("Glyph cannot exceed {count} characters.").format(count=GLYPH_MAX_LENGTH))

    return parsed.model_dump(exclude_none=True)


def format_issue_context(context: dict[str, Any] | None) -> str:
    """The context in words, in the active language: "Al-Baqarah 2:255", "Page 12", …; "" when empty.

    Reads only the stored keys, so it never needs the asset (no extra queries)
    and tolerates any shape an older row might hold.
    """
    if not context or not isinstance(context, dict):
        return ""
    parts: list[str] = []
    surah = context.get("surah")
    if isinstance(surah, int) and surah in QURAN_SURAHS:
        meta = QURAN_SURAHS[surah]
        name = meta["name"] if (get_language() or "").startswith("ar") else meta["name_en"]
        ayah = context.get("ayah")
        parts.append(f"{name} {surah}:{ayah}" if ayah is not None else f"{name} ({surah})")
    if context.get("page") is not None:
        parts.append(_("Page {page}").format(page=context["page"]))
    if context.get("glyph"):
        parts.append(_("Glyph “{glyph}”").format(glyph=context["glyph"]))
    return " · ".join(parts)
