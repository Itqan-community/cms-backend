from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.translation import gettext_lazy as _

from apps.core.ninja_utils.errors import ItqanError
from apps.quran.repositories.quran import QuranRepository

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.quran.models import Ayah, Surah, Word


class QuranService:
    """Business logic for serving Quran reference data."""

    def __init__(self, repo: QuranRepository) -> None:
        self.repo = repo

    def list_surahs(self) -> QuerySet[Surah]:
        return self.repo.list_surahs()

    def get_surah(self, surah_id: int) -> Surah:
        surah = self.repo.get_surah(surah_id)
        if surah is None:
            raise ItqanError(
                error_name="surah_not_found",
                message=_("Surah does not exist."),
                status_code=404,
            )
        return surah

    def get_ayah(self, surah_id: int, number_in_surah: int) -> Ayah:
        # Ensure the surah exists so a missing surah and a missing ayah are
        # reported distinctly.
        self.get_surah(surah_id)
        ayah = self.repo.get_ayah(surah_id, number_in_surah)
        if ayah is None:
            raise ItqanError(
                error_name="ayah_not_found",
                message=_("Ayah does not exist."),
                status_code=404,
            )
        return ayah

    def list_ayahs_for_surah(self, surah_id: int) -> QuerySet[Ayah]:
        self.get_surah(surah_id)
        return self.repo.list_ayahs_for_surah(surah_id)

    def list_hierarchy_tree(self) -> QuerySet[Surah]:
        return self.repo.list_hierarchy_tree()

    def list_surah_ayah_tree(self, surah_id: int) -> QuerySet[Ayah]:
        self.get_surah(surah_id)
        return self.repo.list_surah_ayah_tree(surah_id)

    def get_ayah_words(self, surah_id: int, number_in_surah: int) -> QuerySet[Word]:
        words = self.repo.get_ayah_words(surah_id, number_in_surah)
        if words is None:
            raise ItqanError(
                error_name="ayah_not_found",
                message=_("Ayah does not exist."),
                status_code=404,
            )
        return words
