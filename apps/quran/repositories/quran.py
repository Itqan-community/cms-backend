from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count

from apps.quran.models import Ayah, Sura, Word

if TYPE_CHECKING:
    from django.db.models import QuerySet


class QuranRepository:
    """Data-access layer for canonical Quran reference data."""

    def __init__(self) -> None:
        self.sura_model = Sura
        self.ayah_model = Ayah
        self.word_model = Word

    def list_suras(self) -> QuerySet[Sura]:
        return self.sura_model.objects.all()

    def get_sura(self, sura_id: int) -> Sura | None:
        try:
            return self.sura_model.objects.get(pk=sura_id)
        except self.sura_model.DoesNotExist:
            return None

    def list_ayahs_for_sura(self, sura_id: int) -> QuerySet[Ayah]:
        return self.ayah_model.objects.filter(sura_id=sura_id).prefetch_related("words").order_by("number_in_sura")

    def get_ayah(self, sura_id: int, number_in_sura: int) -> Ayah | None:
        try:
            return (
                self.ayah_model.objects.select_related("sura")
                .prefetch_related("words")
                .get(sura_id=sura_id, number_in_sura=number_in_sura)
            )
        except self.ayah_model.DoesNotExist:
            return None

    def list_hierarchy_tree(self) -> QuerySet[Sura]:
        return self.sura_model.objects.all().order_by("id")

    def list_surah_ayah_tree(self, sura_id: int) -> QuerySet[Ayah]:
        return (
            self.ayah_model.objects.filter(sura_id=sura_id)
            .annotate(words_count=Count("words"))
            .order_by("number_in_sura")
        )

    def get_ayah_words(self, sura_id: int, number_in_sura: int) -> QuerySet[Word] | None:
        if not self.ayah_model.objects.filter(sura_id=sura_id, number_in_sura=number_in_sura).exists():
            return None
        return self.word_model.objects.filter(sura_id=sura_id, ayah__number_in_sura=number_in_sura).order_by(
            "position_in_ayah"
        )
