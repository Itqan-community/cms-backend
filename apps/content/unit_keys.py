"""One integer per content unit, whatever the asset's template.

Every content pipeline (entries, changes, snapshots, diffs, the grid) keys a
cell by ``(unit_id, column_key)``. For the single-unit templates the unit id is
the sura / ayah / word id or the page number. A group row (ayah_group /
word_group template) covers a range, so its id encodes both ends:
``from_id * GROUP_KEY_BASE + to_id``. ``GROUP_KEY_BASE`` is above every
``Ayah.id`` (6,236) and ``Word.id`` (77,431), so a group key never collides
with a single unit id within one asset, and ordering keys orders groups by
start, then end.

Kept free of model imports so the models themselves can use it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from functools import reduce
import operator

from django.db.models import BigIntegerField, F, Q
from django.db.models.functions import Cast, Coalesce

GROUP_KEY_BASE = 1_000_000

# The unit columns of AssetVersionEntry / AssetVersionChange, in the order
# ``unit_key_of`` reads them.
UNIT_VALUE_FIELDS: tuple[str, ...] = (
    "sura_id",
    "ayah_id",
    "word_id",
    "page_no",
    "from_ayah_id",
    "to_ayah_id",
    "from_word_id",
    "to_word_id",
)


def encode_group_key(from_id: int, to_id: int) -> int:
    """The unit id of the range ``from_id``..``to_id``."""
    return from_id * GROUP_KEY_BASE + to_id


def decode_group_key(key: int) -> tuple[int, int]:
    """``(from_id, to_id)`` of a group key."""
    return divmod(key, GROUP_KEY_BASE)


def unit_key_of(values: Sequence[int | None]) -> int:
    """The unit id of a row from its ``UNIT_VALUE_FIELDS`` values.

    Tested explicitly against ``None`` rather than by truthiness, so a
    legitimate zero would not fall through to the next unit.
    """
    sura_id, ayah_id, word_id, page_no, from_ayah_id, to_ayah_id, from_word_id, to_word_id = values
    for unit in (sura_id, ayah_id, word_id, page_no):
        if unit is not None:
            return unit
    if from_ayah_id is not None:
        return encode_group_key(from_ayah_id, to_ayah_id)
    return encode_group_key(from_word_id, to_word_id)


def _pair_key(prefix: str) -> F:
    # Cast first: the FK columns are smallint/integer, and `* GROUP_KEY_BASE` overflows int4.
    return Cast(F(f"from_{prefix}_id"), BigIntegerField()) * GROUP_KEY_BASE + F(f"to_{prefix}_id")


def unit_key_expression() -> Coalesce:
    """SQL twin of ``unit_key_of`` for annotating entry / change querysets."""
    return Coalesce(
        "sura_id",
        "ayah_id",
        "word_id",
        "page_no",
        _pair_key("ayah"),
        _pair_key("word"),
        output_field=BigIntegerField(),
    )


def unit_q(unit_ids: Iterable[int]) -> Q:
    """Entry / change rows of the given units, for an asset of any template."""
    ids = list(unit_ids)
    singles = [unit_id for unit_id in ids if unit_id < GROUP_KEY_BASE]
    q = Q(sura_id__in=singles) | Q(ayah_id__in=singles) | Q(word_id__in=singles) | Q(page_no__in=singles)
    pairs = [decode_group_key(unit_id) for unit_id in ids if unit_id >= GROUP_KEY_BASE]
    return reduce(
        operator.or_,
        (Q(from_ayah_id=f, to_ayah_id=t) | Q(from_word_id=f, to_word_id=t) for f, t in pairs),
        q,
    )
