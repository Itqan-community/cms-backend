"""Portal endpoints for an asset's language renditions (list + add).

Auto-discovered and registered under ``/portal/`` like the other portal routers.
Reuses ``_resolve`` from ``asset_content`` so category resolution and per-category
permission enforcement stay in one place.
"""

from typing import Literal

from ninja import File, Form, Schema, UploadedFile

from apps.content.api.portal.asset_content import _resolve
from apps.content.models import AssetLanguage, CategoryChoice
from apps.content.services.asset_language import AssetLanguageService
from apps.content.services.tafsir import TafsirService
from apps.content.services.translation import TranslationService
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
        400: NinjaErrorResponse[Literal["language_exists"]] | NinjaErrorResponse[Literal["content_file_unparseable"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def add_language(
    request: Request,
    category: str,
    slug: str,
    data: Form[AddLanguageIn],
    file: UploadedFile | None = File(None),
) -> AssetLanguage:
    """Register a language for the asset, optionally seeding it from an uploaded file.

    When a file is provided it becomes the language's first published version and
    is parsed into per-ayah entries — so a translator can add a language and upload
    its content in one step.
    """
    resolved = _resolve(category, request, write=True)
    asset_language = AssetLanguageService().add_language(
        slug, resolved, language=data.language, publisher_q=request.publisher_q()
    )
    if file is not None:
        publisher_q = request.publisher_q()
        if resolved == CategoryChoice.TAFSIR:
            TafsirService().create_tafsir_version(
                slug, name="v1", file=file, language=data.language, publisher_q=publisher_q
            )
        else:
            TranslationService().create_translation_version(
                slug, name="v1", file=file, language=data.language, publisher_q=publisher_q
            )
    return asset_language
