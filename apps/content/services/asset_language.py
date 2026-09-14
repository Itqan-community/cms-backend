"""Business logic for an asset's language renditions (source + translations).

An asset carries one source-language rendition plus any number of translations,
each an ``AssetLanguage`` row. This service lists them and adds new (translation)
languages; the source language is created implicitly (see
``Asset.get_or_create_source_language``) and is never added here.
"""

from __future__ import annotations

from django.db.models import Q
from django.utils.translation import gettext as _

from apps.content.models import Asset, AssetLanguage, CategoryChoice
from apps.content.services.asset_content import AssetContentService
from apps.core.ninja_utils.errors import ItqanError


class AssetLanguageService:
    def __init__(self) -> None:
        self._content = AssetContentService()

    def _asset(self, slug: str, category: CategoryChoice, publisher_q: Q | None = None) -> Asset:
        return self._content._get_asset_or_404(slug, category, publisher_q=publisher_q)

    def list_languages(
        self, slug: str, category: CategoryChoice, *, publisher_q: Q | None = None
    ) -> list[AssetLanguage]:
        """Return the asset's languages, source first. Ensures the source exists."""
        asset = self._asset(slug, category, publisher_q)
        asset.get_or_create_source_language()
        return list(asset.languages.order_by("-is_source", "language"))

    def add_language(
        self, slug: str, category: CategoryChoice, *, language: str, publisher_q: Q | None = None
    ) -> AssetLanguage:
        """Add a translation language to the asset (never the source)."""
        asset = self._asset(slug, category, publisher_q)
        asset.get_or_create_source_language()
        if asset.languages.filter(language=language).exists():
            raise ItqanError(
                error_name="language_exists",
                message=_("Language {language} already exists for this asset.").format(language=language),
                status_code=400,
            )
        return AssetLanguage.objects.create(asset=asset, language=language, is_source=False)

    def get_asset_language_or_404(self, asset: Asset, language: str) -> AssetLanguage:
        obj = asset.languages.filter(language=language).first()
        if obj is None:
            raise ItqanError(
                error_name="language_not_available",
                message=_("Language {language} is not available for this asset.").format(language=language),
                status_code=404,
            )
        return obj
