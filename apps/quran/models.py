from django.db import models

from apps.core.models import BaseModel


class RevelationType(models.TextChoices):
    """Place of revelation of a surah."""

    MECCAN = "Meccan", "Meccan"
    MEDINAN = "Medinan", "Medinan"


class Surah(BaseModel):
    """A chapter of the Quran (114 total).

    The primary key mirrors the canonical surah number (1-114) so that foreign
    keys from Ayah/Word map directly onto the source data.
    """

    id = models.PositiveSmallIntegerField(primary_key=True, help_text="Canonical surah number (1-114)")
    name = models.CharField(max_length=64, help_text="Arabic name of the surah")
    transliterated_name = models.CharField(max_length=64, help_text="Latin transliteration of the name")
    english_name = models.CharField(max_length=128, help_text="English meaning of the name")
    ayahs_count = models.PositiveSmallIntegerField(help_text="Number of ayahs in this surah")
    start_offset = models.PositiveSmallIntegerField(
        help_text="Cumulative number of ayahs in all preceding surahs",
    )
    revelation_type = models.CharField(
        max_length=8,
        choices=RevelationType,
        help_text="Whether the surah was revealed in Mecca or Medina",
    )
    revelation_order = models.PositiveSmallIntegerField(help_text="Order in which the surah was revealed")
    rukus_count = models.PositiveSmallIntegerField(help_text="Number of rukus (sections) in this surah")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"Surah({self.id}, {self.name})"


class Ayah(BaseModel):
    """A single ayah (verse) of the Quran (6236 total).

    The primary key mirrors the canonical global ayah index (1-6236).
    """

    id = models.PositiveSmallIntegerField(primary_key=True, help_text="Canonical global ayah index (1-6236)")
    surah = models.ForeignKey(Surah, on_delete=models.CASCADE, related_name="ayahs")
    number_in_surah = models.PositiveSmallIntegerField(help_text="Ayah number within its surah (1-based)")
    text = models.TextField(help_text="Uthmani text of the ayah")
    juz = models.PositiveSmallIntegerField(help_text="Juz (part) number this ayah belongs to (1-30)")
    hizb_quarter = models.PositiveSmallIntegerField(help_text="Hizb quarter number this ayah belongs to")
    page = models.PositiveSmallIntegerField(help_text="Mushaf page number this ayah appears on")

    @property
    def text_uthmani(self) -> str:
        """Alias for backward compatibility with API contract."""
        return self.text

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["surah", "number_in_surah"], name="unique_ayah_per_surah"),
        ]
        indexes = [
            models.Index(fields=["surah", "number_in_surah"]),
            models.Index(fields=["page"]),
        ]

    def __str__(self):
        return f"Ayah({self.surah_id}:{self.number_in_surah})"


class Word(BaseModel):
    """A single word within an ayah (~77431 total).

    The primary key mirrors the canonical global word index.
    """

    id = models.PositiveIntegerField(primary_key=True, help_text="Canonical global word index")
    surah = models.ForeignKey(Surah, on_delete=models.CASCADE, related_name="words")
    ayah = models.ForeignKey(Ayah, on_delete=models.CASCADE, related_name="words")
    position_in_ayah = models.PositiveSmallIntegerField(help_text="Word position within its ayah (1-based)")
    text = models.CharField(max_length=128, help_text="The word text")

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["ayah", "position_in_ayah"]),
        ]

    def __str__(self):
        return f"Word({self.id}, {self.text})"
