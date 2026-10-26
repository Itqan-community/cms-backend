"""The single place the surah / ayah / word / page / group branch lives.

Every consumer — the entries endpoint, the patch path, the diff pipeline, the
importer and the CSV export — asks this module which column an asset's entries
are keyed to and what its canonical unit set is, rather than branching on
``Asset.template`` itself.

The group templates (ayah_group / word_group) have no canonical unit set: their
units are the ranges stored in a version, each keyed by an encoded int
(``apps.content.unit_keys``), so every caller keeps handling plain ``int``
unit ids.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import reduce
import operator
import re
from typing import Literal

from django.db.models import F, Func, OuterRef, Q, QuerySet, Subquery, TextField, Value
from django.db.models.expressions import Combinable
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _

from apps.content.models import GROUP_TEMPLATES, Asset, AssetTemplateChoice, AssetVersion, AssetVersionEntry
from apps.content.unit_keys import decode_group_key, encode_group_key
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
    # Group templates only: the range's ends as (sura, ayah) or (sura, ayah, word),
    # and whether a translated language holds text for a range its source lacks.
    group_from: tuple[int, ...] | None = None
    group_to: tuple[int, ...] | None = None
    orphaned: bool = False


# A group row's reference text (the covered Quran text) is cut here in the grid;
# exports carry it in full.
REFERENCE_TEXT_LIMIT = 500


def unit_position(unit: Ayah | Word) -> tuple[int, ...]:
    """``(sura, ayah)`` of an ayah, ``(sura, ayah, word)`` of a word."""
    if isinstance(unit, Word):
        return (unit.sura_id, unit.ayah.number_in_sura, unit.position_in_ayah)
    return (unit.sura_id, unit.number_in_sura)


def group_label(start: Ayah | Word, end: Ayah | Word) -> str:
    """``"2:1 → 2:5"`` / ``"2:255:1 → 2:255:4"``; a one-unit range is just ``"2:3"``."""
    first = ":".join(map(str, unit_position(start)))
    if start.pk == end.pk:
        return first
    return f"{first} → {':'.join(map(str, unit_position(end)))}"


@dataclass(frozen=True)
class QuranPosition:
    """A position in the mushaf: an ayah, or a word when ``word`` is set (1-based)."""

    surah: int
    ayah: int
    word: int | None = None


def range_invalid_error() -> ItqanError:
    return ItqanError(
        error_name="group_range_invalid",
        message=_("This range doesn't exist in the Quran, or it ends before it starts."),
        status_code=400,
    )


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


# Key of ``EntryFilters.cells`` / ``source_cells`` for "the asset's first column",
# which the grid's legacy ``text`` / ``source_text`` filters name.
FIRST_COLUMN = ""


@dataclass(frozen=True)
class EntryFilters:
    """Column filters for the entries grid, applied to the whole unit set before paging.

    ``cells`` filter the version's own text and ``source_cells`` the source
    language's, both keyed by text column and treating a missing cell as "".
    ``surah`` and ``sura`` both filter the surah number — the grid's
    surah-name dropdown and its surah-number column — and must both match.
    """

    cells: Mapping[str, ColumnFilter] = field(default_factory=dict)
    reference_text: ColumnFilter | None = None
    source_cells: Mapping[str, ColumnFilter] = field(default_factory=dict)
    surah: ColumnFilter | None = None
    sura: ColumnFilter | None = None
    aya: ColumnFilter | None = None

    def for_columns(self, column_keys: Sequence[str]) -> EntryFilters:
        """These filters with ``FIRST_COLUMN`` resolved to the asset's first key.

        Raises ``unknown_filter_column`` for a column the asset doesn't have —
        typically one deleted while the grid still filtered on it.
        """

        def resolve(filters: Mapping[str, ColumnFilter]) -> dict[str, ColumnFilter]:
            resolved = {}
            for key, cell_filter in filters.items():
                resolved[column_keys[0] if key == FIRST_COLUMN else key] = cell_filter
            return resolved

        cells, source_cells = resolve(self.cells), resolve(self.source_cells)
        unknown = sorted((set(cells) | set(source_cells)) - set(column_keys))
        if unknown:
            raise ItqanError(
                error_name="unknown_filter_column",
                message=_("This asset has no column named {columns}.").format(columns=", ".join(unknown)),
                status_code=400,
            )
        return replace(self, cells=cells, source_cells=source_cells)

    @property
    def active(self) -> bool:
        return bool(self.cells or self.source_cells) or any(
            f is not None for f in (self.reference_text, self.surah, self.sura, self.aya)
        )


@dataclass(frozen=True)
class UnitSpec:
    template: AssetTemplateChoice
    field: str
    fk_field: str | None

    @property
    def is_group(self) -> bool:
        return self.template in GROUP_TEMPLATES

    @property
    def range_fields(self) -> tuple[str, str]:
        """The (from, to) columns of a group template's rows."""
        if self.template == AssetTemplateChoice.AYAH_GROUP:
            return ("from_ayah_id", "to_ayah_id")
        if self.template == AssetTemplateChoice.WORD_GROUP:
            return ("from_word_id", "to_word_id")
        raise ValueError(f"{self.template} is not a group template")

    def unit_columns(self, unit_id: int) -> dict[str, int]:
        """The entry / change kwargs that store ``unit_id``."""
        if self.is_group:
            from_field, to_field = self.range_fields
            start, end = decode_group_key(unit_id)
            return {from_field: start, to_field: end}
        return {self.field + ("_id" if self.fk_field else ""): unit_id}

    def entries_q(self, unit_ids: Sequence[int]) -> Q:
        """Narrows an entry / change queryset to these units."""
        ids = list(unit_ids)
        if not ids:
            return Q(pk__in=[])
        if not self.is_group:
            return Q(**{f"{self.field}__in": ids})
        from_field, to_field = self.range_fields
        return reduce(
            operator.or_,
            (Q(**{from_field: start, to_field: end}) for start, end in map(decode_group_key, ids)),
        )

    def order_for(self, unit_id: int) -> int:
        """The stored ``order`` of a unit: its start for a group (an encoded key overflows int4)."""
        return decode_group_key(unit_id)[0] if self.is_group else unit_id

    def first_unit_id(self) -> int | None:
        """The first ayah / word of a group template (None with no Quran data)."""
        model = Ayah if self.template == AssetTemplateChoice.AYAH_GROUP else Word
        return model.objects.order_by("id").values_list("id", flat=True).first()

    def key_for_range(self, start: QuranPosition, end: QuranPosition) -> int:
        """The group key of ``start``..``end``, resolved in one query.

        Raises ``group_range_invalid`` for a position that doesn't exist, a word
        given to an ayah group (or missing from a word group), or an end before
        the start.
        """
        words = self.template == AssetTemplateChoice.WORD_GROUP
        if not self.is_group or any((position.word is not None) != words for position in (start, end)):
            raise range_invalid_error()
        if words:
            found = {
                (sura, aya, word): pk
                for pk, sura, aya, word in Word.objects.filter(
                    reduce(
                        operator.or_,
                        (
                            Q(sura_id=p.surah, ayah__number_in_sura=p.ayah, position_in_ayah=p.word)
                            for p in (start, end)
                        ),
                    )
                ).values_list("id", "sura_id", "ayah__number_in_sura", "position_in_ayah")
            }
        else:
            found = {
                (sura, aya, None): pk
                for pk, sura, aya in Ayah.objects.filter(
                    reduce(operator.or_, (Q(sura_id=p.surah, number_in_sura=p.ayah) for p in (start, end)))
                ).values_list("id", "sura_id", "number_in_sura")
            }
        start_id = found.get((start.surah, start.ayah, start.word))
        end_id = found.get((end.surah, end.ayah, end.word))
        if start_id is None or end_id is None or start_id > end_id:
            raise range_invalid_error()
        return encode_group_key(start_id, end_id)

    def group_units(self, ids: Iterable[int]) -> dict[int, Ayah | Word]:
        """The ayahs / words of a group template, by id, in one query."""
        if self.template == AssetTemplateChoice.AYAH_GROUP:
            return Ayah.objects.in_bulk(list(ids))
        return Word.objects.select_related("ayah").in_bulk(list(ids))

    def stored_ranges(self, version: AssetVersion, *, with_text: bool = False) -> set[int]:
        """The group keys a version has any cell for (``with_text``: any non-blank cell).

        Reads the range columns only, never the text.
        """
        entries = version.entries.exclude(text="") if with_text else version.entries.all()
        pairs = entries.values_list(*self.range_fields).distinct()
        return {encode_group_key(start, end) for start, end in pairs}

    def _covered_texts(self, pairs: Iterable[tuple[int, int]]) -> dict[int, str]:
        """Every covered ayah / word's text, by id, in one query."""
        pairs = list(pairs)
        if not pairs:
            return {}
        model = Ayah if self.template == AssetTemplateChoice.AYAH_GROUP else Word
        covered = reduce(operator.or_, (Q(id__gte=start, id__lte=end) for start, end in pairs))
        return dict(model.objects.filter(covered).values_list("id", "text"))

    @staticmethod
    def _joined(start: int, end: int, texts: Mapping[int, str], limit: int | None = None) -> str:
        """The covered text of ``start``..``end``, cut at ``limit`` characters with "…"."""
        joined = ""
        for unit_id in range(start, end + 1):
            if unit_id in texts:
                joined = f"{joined} {texts[unit_id]}" if joined else texts[unit_id]
            if limit is not None and len(joined) > limit:
                return joined[:limit] + "…"
        return joined

    def _group_keys(self, version: AssetVersion | None, source_version: AssetVersion | None) -> dict[int, bool]:
        """``{key: orphaned}`` in key order.

        A translated language (``source_version`` given) lists its source's
        ranges, plus its own ranges the source lacks, flagged orphaned.
        """
        range_version = source_version or version
        if range_version is None:
            return {}
        keys = dict.fromkeys(self.stored_ranges(range_version), False)
        if source_version is not None and version is not None:
            for key in self.stored_ranges(version):
                keys.setdefault(key, True)
        return dict(sorted(keys.items()))

    def _group_texts(self, version: AssetVersion | None, column_key: str) -> dict[int, str]:
        if version is None:
            return {}
        rows = version.entries.filter(column__key=column_key).values_list(*self.range_fields, "text")
        return {encode_group_key(start, end): text for start, end, text in rows}

    def _filter_groups(
        self,
        keys: list[int],
        sura: int | None,
        filters: EntryFilters | None,
        version: AssetVersion | None,
        source_version: AssetVersion | None,
    ) -> list[int]:
        """Narrow group keys in Python, like pages: ranges have no table to query.

        Surah / ayah conditions test the range's start; the reference-text
        condition tests the whole covered text, as the grid shows it.
        """
        filters = filters if filters is not None and filters.active else None
        by_start = filters is not None and any(
            f is not None for f in (filters.reference_text, filters.surah, filters.sura, filters.aya)
        )
        starts = self.group_units({decode_group_key(key)[0] for key in keys}) if sura is not None or by_start else {}
        covered = (
            self._covered_texts(map(decode_group_key, keys))
            if filters is not None and filters.reference_text is not None
            else {}
        )
        own = {key: self._group_texts(version, key) for key in (filters.cells if filters else {})}
        source = {key: self._group_texts(source_version, key) for key in (filters.source_cells if filters else {})}
        kept = []
        for key in keys:
            start = starts.get(decode_group_key(key)[0])
            if sura is not None and (start is None or start.sura_id != sura):
                continue
            if filters is not None:
                if any(not f.matches(own[k].get(key, "")) for k, f in filters.cells.items()):
                    continue
                if any(not f.matches(source[k].get(key, "")) for k, f in filters.source_cells.items()):
                    continue
                if by_start:
                    position = unit_position(start) if start is not None else (None, None)
                    checks = (
                        (filters.reference_text, self._joined(*decode_group_key(key), covered)),
                        (filters.surah, position[0]),
                        (filters.sura, position[0]),
                        (filters.aya, position[1]),
                    )
                    if any(f is not None and not f.matches(value) for f, value in checks):
                        continue
            kept.append(key)
        return kept

    def group_rows(self, window: list[int], orphaned: dict[int, bool]) -> list[UnitRow]:
        """``UnitRow``s for one page of group keys: two queries whatever the page size."""
        if not window:
            return []
        pairs = [decode_group_key(key) for key in window]
        ends = self.group_units({unit for pair in pairs for unit in pair})
        texts = self._covered_texts(pairs)
        rows = []
        for key, (start_id, end_id) in zip(window, pairs, strict=True):
            start, end = ends[start_id], ends[end_id]
            reference = self._joined(start_id, end_id, texts, REFERENCE_TEXT_LIMIT)
            first = unit_position(start)
            rows.append(
                UnitRow(
                    unit_id=key,
                    label=group_label(start, end),
                    reference_text=reference,
                    sura=first[0],
                    aya=first[1],
                    order=key,
                    group_from=first,
                    group_to=unit_position(end),
                    orphaned=orphaned[key],
                )
            )
        return rows

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
        ``units_page`` returns, not this. A group template has no canonical
        unit set: 0 (its rows are a version's stored ranges, see ``units_page``).
        """
        if self.is_group:
            return 0
        if self.template == AssetTemplateChoice.SURAH:
            return Sura.objects.count()
        if self.template == AssetTemplateChoice.AYAH:
            return Ayah.objects.count()
        if self.template == AssetTemplateChoice.WORD:
            return Word.objects.count()
        return asset.mushaf_layout.page_count

    def _entry_text(self, version: AssetVersion | None, column_key: str) -> Coalesce | Value:
        """Annotation: the unit's stored cell in ``version``'s column, or "" when it has none."""
        if version is None:
            return Value("", output_field=TextField())
        stored = AssetVersionEntry.objects.filter(
            version=version, column__key=column_key, **{self.field: OuterRef("pk")}
        ).values("text")[:1]
        return Coalesce(Subquery(stored), Value(""), output_field=TextField())

    def _filter_queryset(
        self,
        qs: QuerySet,
        filters: EntryFilters,
        version: AssetVersion | None,
        source_version: AssetVersion | None,
    ) -> QuerySet:
        """Narrow a surah/ayah/word queryset by the grid's column filters."""
        for index, (key, cell_filter) in enumerate(filters.cells.items()):
            name = f"_cell_{index}"
            qs = qs.annotate(**{name: _normalized(self._entry_text(version, key))}).filter(cell_filter.q(name))
        for index, (key, cell_filter) in enumerate(filters.source_cells.items()):
            name = f"_source_{index}"
            qs = qs.annotate(**{name: _normalized(self._entry_text(source_version, key))}).filter(cell_filter.q(name))
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

        def texts(version: AssetVersion | None, keys: Sequence[str]) -> dict[tuple[int, str], str]:
            if version is None or not keys:
                return {}
            rows = version.entries.filter(page_no__isnull=False, column__key__in=keys).values_list(
                "page_no", "column__key", "text"
            )
            return {(page, key): text for page, key, text in rows}

        own = texts(version, list(filters.cells))
        source = texts(source_version, list(filters.source_cells))
        kept = []
        for page in pages:
            if any(not f.matches(own.get((page, key), "")) for key, f in filters.cells.items()):
                continue
            if any(not f.matches(source.get((page, key), "")) for key, f in filters.source_cells.items()):
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
        where the ``cells`` / ``source_cells`` filters read stored text from
        (``source_version`` is None when there is no source to compare to).
        """
        if self.is_group:
            keys = self._group_keys(version, source_version)
            kept = self._filter_groups(list(keys), sura, filters, version, source_version)
            return self.group_rows(kept[offset : offset + limit], keys), len(kept)
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
        if self.is_group:
            pairs = {candidate: decode_group_key(candidate) for candidate in candidates}
            existing = self.group_units({unit for pair in pairs.values() for unit in pair})
            return {c for c, (start, end) in pairs.items() if start in existing and end in existing and start <= end}
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
    AssetTemplateChoice.AYAH_GROUP: UnitSpec(AssetTemplateChoice.AYAH_GROUP, "ayah_range", None),
    AssetTemplateChoice.WORD_GROUP: UnitSpec(AssetTemplateChoice.WORD_GROUP, "word_range", None),
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
