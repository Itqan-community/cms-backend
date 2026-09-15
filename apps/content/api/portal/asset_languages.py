"""Portal endpoints for an asset's language renditions (list + add).

Auto-discovered and registered under ``/portal/`` like the other portal routers.
Reuses ``_resolve`` from ``asset_content`` so category resolution and per-category
permission enforcement stay in one place.
"""

from typing import Literal

from django.db import transaction
from ninja import File, Form, Schema, UploadedFile

from apps.content.api.portal.asset_content import _resolve
from apps.content.models import AssetLanguage, CategoryChoice, StatusChoice
from apps.content.services.asset_language import AssetLanguageService
from apps.content.services.asset_language_access import (
    allowed_languages,
    assign_language_to_member,
    require_language,
)
from apps.content.services.tafsir import TafsirService
from apps.content.services.translation import TranslationService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])


class LanguageOut(Schema):
    language: str
    is_source: bool
    is_available: bool

    @staticmethod
    def resolve_is_available(obj: AssetLanguage) -> bool:
        return obj.status == StatusChoice.READY


class AddLanguageIn(Schema):
    language: str


class LanguageAvailabilityIn(Schema):
    available: bool


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
    """The asset's languages, narrowed to the ones this member works in.

    Holders of ``PORTAL_ACCESS_ALL_LANGUAGES`` see them all.
    """
    resolved = _resolve(category, request, write=False)
    languages = AssetLanguageService().list_languages(slug, resolved, publisher_q=request.publisher_q())
    if not languages:
        return languages
    allowed = allowed_languages(request.user, languages[0].asset)
    return [rendition for rendition in languages if rendition.language in allowed]


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
@permission_required([permission_class(PermissionChoice.PORTAL_ADD_ASSET_LANGUAGE)])
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

    Gated by ``PORTAL_ADD_ASSET_LANGUAGE`` rather than the content-edit permission,
    so who may start a new language is controlled separately from who may edit one.
    The new language is assigned to the creator's membership, otherwise they would
    immediately be unable to edit what they just created.
    """
    resolved = _resolve(category, request, write=False)
    publisher_q = request.publisher_q()
    # Register the language and seed its first version atomically: if the upload
    # fails (storage error or an unparseable file), the language registration is
    # rolled back too, so we never leave a language without its requested version.
    with transaction.atomic():
        asset_language = AssetLanguageService().add_language(
            slug, resolved, language=data.language, publisher_q=publisher_q
        )
        assign_language_to_member(request.user, asset_language.asset, data.language)
        if file is not None:
            if resolved == CategoryChoice.TAFSIR:
                TafsirService().create_tafsir_version(
                    slug, name="v1", file=file, language=data.language, strict=True, publisher_q=publisher_q
                )
            else:
                TranslationService().create_translation_version(
                    slug, name="v1", file=file, language=data.language, strict=True, publisher_q=publisher_q
                )
    return asset_language


@router.patch(
    "content/{category}/{slug}/languages/{language}/availability/",
    response={
        200: LanguageOut,
        400: NinjaErrorResponse[Literal["language_has_no_published_version"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["language_not_available"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def set_language_availability(
    request: Request,
    category: str,
    slug: str,
    language: str,
    data: LanguageAvailabilityIn,
) -> AssetLanguage:
    """Mark a language rendition available (READY) or pending (DRAFT) to consumers.

    Making a language available requires at least one published version, so an
    unfinished translation is never advertised to end users.
    """
    resolved = _resolve(category, request, write=True)
    service = AssetLanguageService()
    asset = service.get_asset(slug, resolved, publisher_q=request.publisher_q())
    require_language(request.user, asset, language)
    return service.set_language_status(
        slug, resolved, language=language, available=data.available, publisher_q=request.publisher_q()
    )
