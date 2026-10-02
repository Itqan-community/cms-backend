"""The single place the surah / ayah / word / page branch lives.

Every consumer — the entries endpoint, the patch path, the diff pipeline, the
importer and the CSV export — asks this module which column an asset's entries
are keyed to and what its canonical unit set is, rather than branching on
``Asset.template`` itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import reduce
import operator
import re
from typing import Literal

from django.db.models import F, Func, OuterRef, Q, QuerySet, Subquery, TextField, Value
from django.db.models.expressions import Combinable
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _

from apps.content.models import Asset, AssetTemplateChoice, AssetVersion, AssetVersionEntry
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


TextFilterType = Literal["contains", "notContains", "equals", "notEqual", "startsWith", "endsWith", "blank", "notBlank"]
NumberFilterType = Literal[
    "equals",
    "notEqual",
    "lessThan",
    "lessThanOrEqual",
    "greaterThan",
    "greaterThanOrEqual",
    "inRange",
    "blank",
    "notBlank",
]

# Arabic text filters ignore vocalization: Uthmani Quran text (and much tafsir
# text) carries harakat, Quranic annotation marks and tatweel that nobody types.
# The same normalization runs in Postgres (`_normalized`) and in Python
# (`normalize_arabic`), so both sides of a comparison are stripped alike.
_ARABIC_MARKS = "[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]"
# Alef wasla / hamza / madda forms read as a bare alef; alef maksura as ya.
_ARABIC_LETTERS_FROM = "\u0671\u0623\u0625\u0622\u0649"
_ARABIC_LETTERS_TO = "\u0627\u0627\u0627\u0627\u064a"
_ARABIC_LETTERS = str.maketrans(_ARABIC_LETTERS_FROM, _ARABIC_LETTERS_TO)
_ALEF = "\u0627"
# Characters that are special in both Postgres (ARE) and Python regexes.
_REGEX_SPECIALS = frozenset("\\^$.|?*+()[]{}")
# Anchors around the needle per text filter type; the `not*` types negate it.
_TEXT_PATTERNS: dict[str, str] = {
    "contains": "{}",
    "notContains": "{}",
    "equals": "^{}$",
    "notEqual": "^{}$",
    "startsWith": "^{}",
    "endsWith": "{}$",
}
_NUMBER_LOOKUPS: dict[str, str] = {
    "equals": "exact",
    "notEqual": "exact",
    "lessThan": "lt",
    "lessThanOrEqual": "lte",
    "greaterThan": "gt",
    "greaterThanOrEqual": "gte",
}


def normalize_arabic(text: str) -> str:
    """Strip Arabic vocalization marks and fold letter variants (see `_ARABIC_MARKS`)."""
    return re.sub(_ARABIC_MARKS, "", text).translate(_ARABIC_LETTERS)


def _normalized(expression: Combinable) -> Func:
    """SQL twin of ``normalize_arabic`` for an annotated text expression."""
    stripped = Func(
        expression,
        Value(_ARABIC_MARKS),
        Value(""),
        Value("g"),
        function="REGEXP_REPLACE",
        output_field=TextField(),
    )
    return Func(
        stripped,
        Value(_ARABIC_LETTERS_FROM),
        Value(_ARABIC_LETTERS_TO),
        function="TRANSLATE",
        output_field=TextField(),
    )


@dataclass(frozen=True)
class TextCondition:
    """One grid text-filter condition over ``normalize_arabic``-ed text.

    Matching is case-insensitive and ignores Arabic vocalization. Every alef
    the user types is optional, because Uthmani spelling often writes it as a
    dagger alef (stripped as a mark): typed العالمين must match ٱلۡعَٰلَمِينَ.
    """

    type: TextFilterType
    value: str = ""

    def _pattern(self) -> str:
        """The needle as a regex valid in both Postgres and Python."""
        needle = "".join(
            f"{_ALEF}?" if char == _ALEF else f"\\{char}" if char in _REGEX_SPECIALS else char
            for char in normalize_arabic(self.value)
        )
        return _TEXT_PATTERNS[self.type].format(needle)

    def q(self, field_name: str) -> Q:
        """The condition on a normalized, non-null text column (see ``_normalized``)."""
        if self.type in ("blank", "notBlank"):
            blank = Q(**{field_name: ""})
            return blank if self.type == "blank" else ~blank
        match = Q(**{f"{field_name}__iregex": self._pattern()})
        return ~match if self.type in ("notContains", "notEqual") else match

    def matches(self, value: str | None) -> bool:
        """Python twin of ``q`` for units with no backing table (pages)."""
        text = normalize_arabic(value or "")
        if self.type in ("blank", "notBlank"):
            return (text == "") == (self.type == "blank")
        found = re.search(self._pattern(), text, re.IGNORECASE) is not None
        return not found if self.type in ("notContains", "notEqual") else found


@dataclass(frozen=True)
class NumberCondition:
    """One grid number-filter condition; ``inRange`` includes both ends."""

    type: NumberFilterType
    value: int | None = None
    value_to: int | None = None

    def q(self, field_name: str) -> Q:
        if self.type in ("blank", "notBlank"):
            return Q(**{f"{field_name}__isnull": self.type == "blank"})
        if self.type == "inRange":
            return Q(**{f"{field_name}__gte": self.value, f"{field_name}__lte": self.value_to})
        match = Q(**{f"{field_name}__{_NUMBER_LOOKUPS[self.type]}": self.value})
        return ~match if self.type == "notEqual" else match

    def matches(self, value: int | None) -> bool:
        """Python twin of ``q`` for units with no backing table (pages)."""
        if self.type in ("blank", "notBlank"):
            return (value is None) == (self.type == "blank")
        if value is None or self.value is None:
            return False
        if self.type == "inRange":
            return self.value_to is not None and self.value <= value <= self.value_to
        return {
            "equals": value == self.value,
            "notEqual": value != self.value,
            "lessThan": value < self.value,
            "lessThanOrEqual": value <= self.value,
            "greaterThan": value > self.value,
            "greaterThanOrEqual": value >= self.value,
        }[self.type]


@dataclass(frozen=True)
class ColumnFilter:
    """One column's grid filter: one or more conditions joined by AND / OR."""

    conditions: tuple[TextCondition | NumberCondition, ...]
    operator: Literal["AND", "OR"] = "AND"

    def q(self, field_name: str) -> Q:
        join = operator.and_ if self.operator == "AND" else operator.or_
        return reduce(join, (condition.q(field_name) for condition in self.conditions))

    def matches(self, value: str | int | None) -> bool:
        results = (condition.matches(value) for condition in self.conditions)
        return all(results) if self.operator == "AND" else any(results)


@dataclass(frozen=True)
class EntryFilters:
    """Column filters for the entries grid, applied to the whole unit set before paging.

    ``text`` is the version's own text and ``source_text`` the source
    language's, both treated as "" for units with no stored entry. ``surah``
    and ``sura`` both filter the surah number — the grid's surah-name dropdown
    and its surah-number column — and must both match.
    """

    text: ColumnFilter | None = None
    reference_text: ColumnFilter | None = None
    source_text: ColumnFilter | None = None
    surah: ColumnFilter | None = None
    sura: ColumnFilter | None = None
    aya: ColumnFilter | None = None

    @property
    def active(self) -> bool:
        return any(
            f is not None for f in (self.text, self.reference_text, self.source_text, self.surah, self.sura, self.aya)
        )


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

    def _entry_text(self, version: AssetVersion | None) -> Coalesce | Value:
        """Annotation: the unit's stored text in ``version``, or "" when it has none."""
        if version is None:
            return Value("", output_field=TextField())
        stored = AssetVersionEntry.objects.filter(version=version, **{self.field: OuterRef("pk")}).values("text")[:1]
        return Coalesce(Subquery(stored), Value(""), output_field=TextField())

    def _filter_queryset(
        self,
        qs: QuerySet,
        filters: EntryFilters,
        version: AssetVersion | None,
        source_version: AssetVersion | None,
    ) -> QuerySet:
        """Narrow a surah/ayah/word queryset by the grid's column filters."""
        if filters.text is not None:
            qs = qs.annotate(_entry_text=_normalized(self._entry_text(version))).filter(filters.text.q("_entry_text"))
        if filters.source_text is not None:
            qs = qs.annotate(_source_text=_normalized(self._entry_text(source_version))).filter(
                filters.source_text.q("_source_text")
            )
        if filters.reference_text is not None:
            reference = "name" if self.template == AssetTemplateChoice.SURAH else "text"
            qs = qs.annotate(_reference_text=_normalized(F(reference))).filter(
                filters.reference_text.q("_reference_text")
            )
        sura_field = "id" if self.template == AssetTemplateChoice.SURAH else "sura_id"
        for sura_filter in (filters.surah, filters.sura):
            if sura_filter is not None:
                qs = qs.filter(sura_filter.q(sura_field))
        if filters.aya is not None:
            # Surah units have no ayah; the grid shows no ayah column for them.
            aya_field = {
                AssetTemplateChoice.AYAH: "number_in_sura",
                AssetTemplateChoice.WORD: "ayah__number_in_sura",
            }.get(self.template)
            if aya_field is not None:
                qs = qs.filter(filters.aya.q(aya_field))
        return qs

    def _filter_pages(
        self,
        pages: range,
        filters: EntryFilters,
        version: AssetVersion | None,
        source_version: AssetVersion | None,
    ) -> list[int]:
        """Narrow the generated page range in Python: pages have no table to query,
        and a layout has at most a few hundred of them."""

        def texts(version: AssetVersion | None) -> dict[int, str]:
            if version is None:
                return {}
            return dict(version.entries.filter(page_no__isnull=False).values_list("page_no", "text"))

        own = texts(version) if filters.text is not None else {}
        source = texts(source_version) if filters.source_text is not None else {}
        kept = []
        for page in pages:
            if filters.text is not None and not filters.text.matches(own.get(page, "")):
                continue
            if filters.source_text is not None and not filters.source_text.matches(source.get(page, "")):
                continue
            # Pages carry no reference text and no surah / ayah number.
            if filters.reference_text is not None and not filters.reference_text.matches(""):
                continue
            if any(f is not None and not f.matches(None) for f in (filters.surah, filters.sura, filters.aya)):
                continue
            kept.append(page)
        return kept

    def units_page(
        self,
        asset: Asset,
        *,
        offset: int,
        limit: int,
        sura: int | None = None,
        filters: EntryFilters | None = None,
        version: AssetVersion | None = None,
        source_version: AssetVersion | None = None,
    ) -> tuple[Sequence[UnitRow], int]:
        """One page of canonical units, plus the total count for that filter.

        The slice is applied to the queryset (or the page range) before any
        ``UnitRow`` is built, so a word-template request never materialises
        77,431 objects. ``filters`` narrow the whole unit set first, so
        ``total`` is the filtered count; ``version`` / ``source_version`` are
        where the ``text`` / ``source_text`` filters read stored text from
        (``source_version`` is None when there is no source to compare to).
        """
        source = self._queryset(asset, sura)
        if filters is not None and filters.active:
            if isinstance(source, range):
                source = self._filter_pages(source, filters, version, source_version)
            else:
                source = self._filter_queryset(source, filters, version, source_version)
        # `range` also has a `.count()`, but with different semantics
        # (`range.count(value)`), so discriminate on the type, not the attribute.
        total = len(source) if isinstance(source, range | list) else source.count()
        window = source[offset : offset + limit]
        return [self._to_row(item) for item in window], total

    def valid_unit_ids(self, asset: Asset, candidates: list[int]) -> set[int]:
        """Which of ``candidates`` are real units of this template.

        Bounded by ``candidates`` rather than the template's full unit set —
        for the word template ``units(asset)`` would materialise 77,431 rows
        on every single save, which this deliberately avoids.
        """
        if self.template == AssetTemplateChoice.PAGE:
            return {c for c in candidates if 1 <= c <= asset.mushaf_layout.page_count}
        model = {"sura": Sura, "ayah": Ayah, "word": Word}[self.field]
        return set(model.objects.filter(id__in=candidates).values_list("id", flat=True))

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


def unit_spec_for_template(template: AssetTemplateChoice) -> UnitSpec:
    """The descriptor for a template, before any asset exists (e.g. on create)."""
    return _SPECS[template]
