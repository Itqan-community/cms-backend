"""The single place the surah / ayah / word / page branch lives.

Every consumer — the entries endpoint, the patch path, the diff pipeline, the
importer and the CSV export — asks this module which column an asset's entries
are keyed to and what its canonical unit set is, rather than branching on
``Asset.template`` itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from django.db.models import QuerySet
from django.utils.translation import gettext as _

from apps.content.models import Asset, AssetTemplateChoice
from apps.core.ninja_utils.errors import ItqanError
from apps.quran.models import Ayah, Sura, Word


@dataclass(frozen=True)
class UnitRow:
    """One canonical unit of a template, before any stored text is overlaid."""

    unit_id: int
    label: str
    reference_text: str
    sura: int | None
    aya: int | None
    order: int


@dataclass(frozen=True)
class UnitSpec:
    template: AssetTemplateChoice
    field: str
    fk_field: str | None

    def _queryset(self, asset: Asset, sura: int | None) -> QuerySet[Sura] | QuerySet[Ayah] | QuerySet[Word] | range:
        """The ordered source of canonical units for this template.

        A queryset for surah/ayah/word; a plain ``range`` for page, since
        pages have no backing table.
        """
        if self.template == AssetTemplateChoice.SURAH:
            qs = Sura.objects.order_by("id")
            if sura is not None:
                qs = qs.filter(id=sura)
            return qs

        if self.template == AssetTemplateChoice.AYAH:
            qs = Ayah.objects.order_by("id")
            if sura is not None:
                qs = qs.filter(sura_id=sura)
            return qs

        if self.template == AssetTemplateChoice.WORD:
            qs = Word.objects.select_related("ayah").order_by("id")
            if sura is not None:
                qs = qs.filter(sura_id=sura)
            return qs

        # page: generated, there is no page table
        if sura is not None:
            return range(0)
        page_count = asset.mushaf_layout.page_count
        return range(1, page_count + 1)

    def _to_row(self, item: Sura | Ayah | Word | int) -> UnitRow:
        """Build one ``UnitRow`` from a single source item, dispatching on the template."""
        if self.template == AssetTemplateChoice.SURAH:
            return UnitRow(
                unit_id=item.id,
                label=f"{item.id}. {item.transliterated_name}",
                reference_text=item.name,
                sura=item.id,
                aya=None,
                order=item.id,
            )

        if self.template == AssetTemplateChoice.AYAH:
            return UnitRow(
                unit_id=item.id,
                label=f"{item.sura_id}:{item.number_in_sura}",
                reference_text=item.text,
                sura=item.sura_id,
                aya=item.number_in_sura,
                order=item.id,
            )

        if self.template == AssetTemplateChoice.WORD:
            return UnitRow(
                unit_id=item.id,
                label=f"{item.sura_id}:{item.ayah.number_in_sura}:{item.position_in_ayah}",
                reference_text=item.text,
                sura=item.sura_id,
                aya=item.ayah.number_in_sura,
                order=item.id,
            )

        # page: `item` is a bare page number from the generated range
        return UnitRow(
            unit_id=item,
            label=_("Page {number}").format(number=item),
            reference_text="",
            sura=None,
            aya=None,
            order=item,
        )

    def total(self, asset: Asset) -> int:
        """The template's full unit count, ignoring any ``sura`` filter.

        Callers paginating a ``sura``-filtered set must use the total that
        ``units_page`` returns, not this.
        """
        if self.template == AssetTemplateChoice.SURAH:
            return Sura.objects.count()
        if self.template == AssetTemplateChoice.AYAH:
            return Ayah.objects.count()
        if self.template == AssetTemplateChoice.WORD:
            return Word.objects.count()
        return asset.mushaf_layout.page_count

    def units_page(
        self, asset: Asset, *, offset: int, limit: int, sura: int | None = None
    ) -> tuple[Sequence[UnitRow], int]:
        """One page of canonical units, plus the total count for that filter.

        The slice is applied to the queryset (or the page range) before any
        ``UnitRow`` is built, so a word-template request never materialises
        77,431 objects.
        """
        source = self._queryset(asset, sura)
        # `range` also has a `.count()`, but with different semantics
        # (`range.count(value)`), so discriminate on the type, not the attribute.
        total = len(source) if isinstance(source, range) else source.count()
        window = source[offset : offset + limit]
        return [self._to_row(item) for item in window], total

    def units(self, asset: Asset, *, sura: int | None = None) -> Sequence[UnitRow]:
        """Every canonical unit of this template, in order.

        Materialises the entire set. That is fine for surah (114) and page
        (a few hundred), and tolerable for ayah (6,236) — but the word
        template has 77,431 units in production, so a request path must call
        ``units_page`` with an explicit limit instead of reaching for this as
        "the easy way to get everything".
        """
        rows, _total = self.units_page(asset, offset=0, limit=self.total(asset), sura=sura)
        return rows


_SPECS: dict[str, UnitSpec] = {
    AssetTemplateChoice.SURAH: UnitSpec(AssetTemplateChoice.SURAH, "sura", "sura"),
    AssetTemplateChoice.AYAH: UnitSpec(AssetTemplateChoice.AYAH, "ayah", "ayah"),
    AssetTemplateChoice.WORD: UnitSpec(AssetTemplateChoice.WORD, "word", "word"),
    AssetTemplateChoice.PAGE: UnitSpec(AssetTemplateChoice.PAGE, "page_no", None),
}


def unit_spec_for(asset: Asset) -> UnitSpec:
    """The descriptor for an asset's template."""
    spec = _SPECS.get(asset.template)
    if spec is None:
        raise ItqanError(
            error_name="asset_template_missing",
            message=_("This asset has no content template."),
            status_code=400,
        )
    return spec
