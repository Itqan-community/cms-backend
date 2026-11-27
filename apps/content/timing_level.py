"""
Timing level of a recitation: how fine-grained its timings are.

Timings are stored per ayah (`RecitationAyahTiming`): the uploaded timing JSON is read
for each ayah's `start` / `end` only, and nothing finer is kept. So the level a
recitation can have today is `ayah` (it has at least one ayah timing) or none.
`word` and `sentence` are part of the contract so clients can show them once finer
timings are stored; nothing produces them yet.

The level is read from an `Exists` annotation (`has_ayah_timings`) on the asset row,
so a list adds one correlated subquery to its main query instead of a query per row.
"""

from typing import Literal

from django.db.models import Exists, OuterRef

from apps.content.models import RecitationAyahTiming

TimingLevel = Literal["ayah", "word", "sentence"]

TIMING_LEVEL_DESCRIPTION = (
    "Finest timing the recitation has: `ayah`, `word` or `sentence`; null without timings. "
    "Only `ayah` is produced today."
)


def has_ayah_timings_exists(*, visible_qualities_only: bool) -> Exists:
    """`Exists` for an asset row (``OuterRef("pk")``) that has at least one ayah timing.

    Consumer surfaces pass ``visible_qualities_only=True``: a hidden quality's timings are
    withdrawn from consumers. The portal counts every quality.
    """
    timings = RecitationAyahTiming.objects.filter(track__asset=OuterRef("pk"))
    if visible_qualities_only:
        timings = timings.filter(track__quality__is_visible=True)
    return Exists(timings)


def timing_level(has_ayah_timings: bool | None) -> TimingLevel | None:
    """The level for an asset annotated with `has_ayah_timings`."""
    return "ayah" if has_ayah_timings else None
