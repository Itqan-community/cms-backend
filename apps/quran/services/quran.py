from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.translation import gettext_lazy as _

from apps.core.ninja_utils.errors import ItqanError
from apps.quran.repositories.quran import QuranRepository

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.quran.models import Ayah, Sura


class QuranService:
    """Business logic for serving Quran reference data."""

    def __init__(self, repo: QuranRepository) -> None:
        self.repo = repo

    def list_suras(self) -> QuerySet[Sura]:
        return self.repo.list_suras()

    def get_sura(self, sura_id: int) -> Sura:
        sura = self.repo.get_sura(sura_id)
        if sura is None:
            raise ItqanError(
                error_name="sura_not_found",
                message=_("Sura does not exist."),
                status_code=404,
            )
        return sura

    def get_ayah(self, sura_id: int, number_in_sura: int) -> Ayah:
        # Ensure the sura exists so a missing sura and a missing ayah are
        # reported distinctly.
        self.get_sura(sura_id)
        ayah = self.repo.get_ayah(sura_id, number_in_sura)
        if ayah is None:
            raise ItqanError(
                error_name="ayah_not_found",
                message=_("Ayah does not exist."),
                status_code=404,
            )
        return ayah

    def list_ayahs_for_sura(self, sura_id: int) -> QuerySet[Ayah]:
        self.get_sura(sura_id)
        return self.repo.list_ayahs_for_sura(sura_id)
