from typing import Literal

from ninja import Field, Schema

from apps.content.services.ai_translation import AiTranslationService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.AI])

FieldKey = Literal["name", "description", "long_description", "bio", "version_name", "version_summary"]
# Caps a single request well inside the free-tier token budget.
MAX_FIELD_LENGTH = 8000


class AiSlugFor(Schema):
    name_ar: str = Field(default="", max_length=255)
    name_en: str = Field(default="", max_length=255)
    language: str = Field(default="", max_length=10)
    reciter_id: int | None = None
    riwayah_id: int | None = None
    year: int | None = None


class AiTranslateIn(Schema):
    mode: Literal["translate", "web"]
    category: Literal["mushaf", "tafsir", "translation", "font", "recitation", "reciter"]
    fields: dict[FieldKey, str] = Field(..., description="Arabic values keyed by field name.")
    context: dict[Literal["reciter", "riwayah"], str] = Field(
        default_factory=dict, description="Optional extra context, e.g. the selected reciter and riwayah names."
    )
    slug_for: AiSlugFor | None = Field(
        default=None,
        description="When set (asset create forms), the same call also suggests the new asset's package slug.",
    )


class AiTranslateOut(Schema):
    fields: dict[str, str] = Field(..., description="English values for the requested fields.")
    sources: list[str] = Field(..., description="Web pages used in `web` mode.")
    slug: str | None = Field(
        ..., description="Suggested package slug for `slug_for`; send it back as `slug` when creating the asset."
    )


@router.post(
    "ai/translate/",
    response={
        200: AiTranslateOut,
        400: NinjaErrorResponse[Literal["ai_translate_empty"]],
        429: NinjaErrorResponse[Literal["ai_quota_exceeded"]] | NinjaErrorResponse[Literal["ai_rate_limited"]],
        503: NinjaErrorResponse[Literal["ai_unavailable"]],
    },
)
@permission_required(
    [
        permission_class(PermissionChoice.PORTAL_CREATE_MUSHAF)
        | permission_class(PermissionChoice.PORTAL_CREATE_TAFSIR)
        | permission_class(PermissionChoice.PORTAL_CREATE_TRANSLATION)
        | permission_class(PermissionChoice.PORTAL_CREATE_FONT)
        | permission_class(PermissionChoice.PORTAL_CREATE_RECITATION)
        | permission_class(PermissionChoice.PORTAL_CREATE_RECITER)
    ]
)
def ai_translate(request: Request, data: AiTranslateIn):
    """Translate Arabic asset metadata to English with the free-tier Gemini API (create forms only)."""
    fields = {key: value[:MAX_FIELD_LENGTH] for key, value in data.fields.items()}
    result = AiTranslationService().translate(
        mode=data.mode,
        category=data.category,
        fields=fields,
        context=dict(data.context),
        slug_for=data.slug_for.model_dump() if data.slug_for else None,
    )
    return 200, {"fields": result.fields, "sources": result.sources, "slug": result.slug}
