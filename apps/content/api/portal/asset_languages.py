"""Portal endpoints for an asset's language renditions (list + add).

Auto-discovered and registered under ``/portal/`` like the other portal routers.
Reuses ``_resolve`` from ``asset_content`` so category resolution and per-category
permission enforcement stay in one place.
"""

from typing import Literal

from ninja import Schema

from apps.content.api.portal.asset_content import _resolve
from apps.content.models import AssetLanguage
from apps.content.services.asset_language import AssetLanguageService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])


class LanguageOut(Schema):
    language: str
    is_source: bool


class AddLanguageIn(Schema):
    language: str


@router.get(
    "content/{category}/{slug}/languages/",
    response={
        200: list[LanguageOut],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def list_languages(request: Request, category: str, slug: str) -> list[AssetLanguage]:
    resolved = _resolve(category, request, write=False)
    return AssetLanguageService().list_languages(slug, resolved, publisher_q=request.publisher_q())


@router.post(
    "content/{category}/{slug}/languages/",
    response={
        200: LanguageOut,
        400: NinjaErrorResponse[Literal["language_exists"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def add_language(request: Request, category: str, slug: str, data: AddLanguageIn) -> AssetLanguage:
    resolved = _resolve(category, request, write=True)
    return AssetLanguageService().add_language(
        slug, resolved, language=data.language, publisher_q=request.publisher_q()
    )
