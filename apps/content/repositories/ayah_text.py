"""ORM access for the public ayah text endpoint (``GET /ayahs/{ayah_key}/``).

Every method is one query whatever the number of assets requested, so the
endpoint's query count stays constant as callers ask for more assets.
"""

from __future__ import annotations

from functools import reduce
import operator

from django.db.models import Exists, OuterRef, Prefetch, Q

from apps.content.columns import Snapshot
from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetVersion,
    AssetVersionEntry,
    StatusChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.unit_keys import UNIT_VALUE_FIELDS
from apps.quran.models import Ayah, Word

# Prefetched onto each asset: its source rendition when consumers may read it.
SERVED_RENDITIONS_ATTR = "served_renditions"

# One entry row: (version_id, *UNIT_VALUE_FIELDS, column_key, text).
EntryRow = tuple


class AyahTextRepository:
    def get_ayahs(self, surah: int, first: int, last: int) -> list[tuple[int, int]]:
        """``(ayah_id, number_in_surah)`` of ayahs ``first``..``last`` of ``surah``, in order."""
        return list(
            Ayah.objects.filter(surah_id=surah, number_in_surah__gte=first, number_in_surah__lte=last)
            .order_by("number_in_surah")
            .values_list("id", "number_in_surah")
        )

    def get_public_assets(self, slugs: list[str]) -> list[Asset]:
        """READY assets on the public-API channel with these slugs, with what the
        endpoint reads (publisher, tags, columns, served source rendition) loaded.

        ``served_renditions`` holds the source rendition when it is READY with a
        published version that was not removed (empty otherwise), its
        ``published_version`` selected and ``published_has_entries`` annotated.
        """
        served = (
            AssetLanguage.objects.filter(
                is_source=True,
                status=StatusChoice.READY,
                published_version__isnull=False,
                published_version__removed_at__isnull=True,
            )
            .select_related("published_version")
            .annotate(
                published_has_entries=Exists(
                    AssetVersionEntry.objects.filter(version_id=OuterRef("published_version_id"))
                )
            )
        )
        return list(
            Asset.objects.filter(slug__in=slugs, status=StatusChoice.READY, in_public_api=True)
            .select_related("publisher")
            .prefetch_related("tags", "columns", Prefetch("languages", queryset=served, to_attr=SERVED_RENDITIONS_ATTR))
        )

    def get_words(self, first_ayah_id: int, last_ayah_id: int) -> list[tuple[int, int, int]]:
        """``(word_id, ayah_id, position_in_ayah)`` of every word in the ayah id range."""
        return list(
            Word.objects.filter(ayah_id__gte=first_ayah_id, ayah_id__lte=last_ayah_id)
            .order_by("id")
            .values_list("id", "ayah_id", "position_in_ayah")
        )

    def get_ayah_keys(self, ayah_ids: set[int]) -> dict[int, tuple[int, int]]:
        """``{ayah_id: (surah, number_in_surah)}``."""
        return {
            ayah_id: (surah, number)
            for ayah_id, surah, number in Ayah.objects.filter(id__in=ayah_ids).values_list(
                "id", "surah_id", "number_in_surah"
            )
        }

    def get_word_positions(self, word_ids: set[int]) -> dict[int, tuple[int, int, int]]:
        """``{word_id: (surah, ayah number_in_surah, position_in_ayah)}``."""
        return {
            word_id: (surah, number, position)
            for word_id, surah, number, position in Word.objects.filter(id__in=word_ids).values_list(
                "id", "ayah__surah_id", "ayah__number_in_surah", "position_in_ayah"
            )
        }

    def get_entry_rows(self, unit_qs: list[Q]) -> list[EntryRow]:
        """Every non-blank cell matching any of ``unit_qs`` (each scopes some versions to a
        unit window), as ``(version_id, *UNIT_VALUE_FIELDS, column_key, text)``."""
        if not unit_qs:
            return []
        return list(
            AssetVersionEntry.objects.filter(reduce(operator.or_, unit_qs))
            .exclude(text="")
            .values_list("version_id", *UNIT_VALUE_FIELDS, "column__key", "text")
        )

    def rebuild_cells(self, version: AssetVersion) -> Snapshot:
        """All cells of a published version that kept only its deltas (a rollback target)."""
        return AssetContentRepository().reconstruct_entries(version)
