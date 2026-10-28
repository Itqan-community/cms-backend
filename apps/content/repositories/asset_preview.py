from __future__ import annotations

from apps.content.models import Asset, AssetLanguage, RecitationSurahTrack
from apps.content.repositories.asset_columns import AssetColumnRepository
from apps.quran.models import Ayah


class AssetPreviewRepository:
    """Reads behind the gallery's recitation and font previews."""

    def first_default_tracks(self, asset: Asset, limit: int) -> list[RecitationSurahTrack]:
        """The first ``limit`` uploaded tracks (by surah) of the asset's default folder,
        while that folder is visible to consumers."""
        return list(
            RecitationSurahTrack.objects.filter(asset=asset, folder__is_default=True, folder__is_visible=True)
            .exclude(audio_file="")
            .order_by("surah_number")[:limit]
        )

    def consumer_rendition(self, asset: Asset, language: str) -> AssetLanguage | None:
        return AssetColumnRepository().consumer_rendition(asset, language)

    def sura_ayahs(self, sura: int) -> list[Ayah]:
        return list(Ayah.objects.filter(sura_id=sura).order_by("number_in_sura"))
