from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count

from apps.quran.models import Ayah, Surah, Word

if TYPE_CHECKING:
    from django.db.models import QuerySet


class QuranRepository:
    """Data-access layer for canonical Quran reference data."""

    def __init__(self) -> None:
        self.surah_model = Surah
        self.ayah_model = Ayah
        self.word_model = Word

    def list_surahs(self) -> QuerySet[Surah]:
        return self.surah_model.objects.all()

    def get_surah(self, surah_id: int) -> Surah | None:
        try:
            return self.surah_model.objects.get(pk=surah_id)
        except self.surah_model.DoesNotExist:
            return None

    def list_ayahs_for_surah(self, surah_id: int) -> QuerySet[Ayah]:
        return self.ayah_model.objects.filter(surah_id=surah_id).prefetch_related("words").order_by("number_in_surah")

    def get_ayah(self, surah_id: int, number_in_surah: int) -> Ayah | None:
        try:
            return (
                self.ayah_model.objects.select_related("surah")
                .prefetch_related("words")
                .get(surah_id=surah_id, number_in_surah=number_in_surah)
            )
        except self.ayah_model.DoesNotExist:
            return None

    def list_hierarchy_tree(self) -> QuerySet[Surah]:
        return self.surah_model.objects.all().order_by("id")

    def list_surah_ayah_tree(self, surah_id: int) -> QuerySet[Ayah]:
        return (
            self.ayah_model.objects.filter(surah_id=surah_id)
            .annotate(words_count=Count("words"))
            .order_by("number_in_surah")
        )

    def get_ayah_words(self, surah_id: int, number_in_surah: int) -> QuerySet[Word] | None:
        if not self.ayah_model.objects.filter(surah_id=surah_id, number_in_surah=number_in_surah).exists():
            return None
        return self.word_model.objects.filter(surah_id=surah_id, ayah__number_in_surah=number_in_surah).order_by(
            "position_in_ayah"
        )
