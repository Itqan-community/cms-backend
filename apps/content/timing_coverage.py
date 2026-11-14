"""
Ayah-timing coverage of recitation tracks, for the portal.

A track is fully timed when it has a timing row for every ayah of its surah. Coverage is
counted in ayahs, not tracks, so a surah with only some ayahs timed shows as partial.
The denominator is the ayahs of the surahs that have tracks: missing surahs are a
separate gap and do not lower timing coverage.
"""

from typing import Literal

from django.db.models import Case, Count, IntegerField, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce, Least
from ninja import Field, Schema

from apps.content.models import RecitationAyahTiming, RecitationSurahTrack
from apps.core.mixins.constants import QURAN_SURAHS

TimingStatus = Literal["none", "partial", "full"]


def surah_ayahs_count_expression() -> Case:
    """`surah_number` -> number of ayahs in that surah, evaluated in SQL on a track row."""
    return Case(
        *(When(surah_number=number, then=Value(surah["ayahs_count"])) for number, surah in QURAN_SURAHS.items()),
        default=Value(0),
        output_field=IntegerField(),
    )


def track_timed_ayahs_expression() -> Least:
    """Ayahs of a track row that have a timing, capped at the surah's ayah count."""
    timings = (
        RecitationAyahTiming.objects.filter(track=OuterRef("pk"))
        .order_by()
        .values("track")
        .annotate(n=Count("id"))
        .values("n")
    )
    return Least(
        Coalesce(Subquery(timings, output_field=IntegerField()), Value(0)),
        surah_ayahs_count_expression(),
    )


def with_track_timing_coverage(tracks):
    """Annotate tracks with `ayahs_count` and `timed_ayahs_count`."""
    return tracks.annotate(ayahs_count=surah_ayahs_count_expression(), timed_ayahs_count=track_timed_ayahs_expression())


def timing_coverage_subqueries(track_filter: Q) -> dict[str, Coalesce]:
    """
    `ayahs_count` / `timed_ayahs_count` annotations summing the tracks matched by
    `track_filter`, which must correlate to the outer row with `OuterRef`
    (e.g. ``Q(asset=OuterRef("pk"))``).
    """
    tracks = with_track_timing_coverage(RecitationSurahTrack.objects.filter(track_filter)).order_by()

    def total(field: str) -> Coalesce:
        summed = tracks.annotate(group=Value(1)).values("group").annotate(total=Sum(field)).values("total")
        return Coalesce(Subquery(summed, output_field=IntegerField()), Value(0))

    return {"ayahs_count": total("ayahs_count"), "timed_ayahs_count": total("timed_ayahs_count")}


def timing_status(timed_ayahs_count: int, ayahs_count: int) -> TimingStatus:
    """`none` without any timed ayah, `full` when every ayah of every track is timed, else `partial`."""
    if timed_ayahs_count <= 0:
        return "none"
    if timed_ayahs_count >= ayahs_count:
        return "full"
    return "partial"


class TimingCoverageOut(Schema):
    """Schema fields for a row annotated by `with_track_timing_coverage` / `timing_coverage_subqueries`."""

    ayahs_count: int = Field(0, description="Ayahs in the surahs that have tracks.")
    timed_ayahs_count: int = Field(0, description="Of those, ayahs that have a timing.")
    timing_status: TimingStatus = Field("none", description="none, partial or full ayah-timing coverage.")

    @staticmethod
    def resolve_ayahs_count(obj: object) -> int:
        return getattr(obj, "ayahs_count", 0) or 0

    @staticmethod
    def resolve_timed_ayahs_count(obj: object) -> int:
        return getattr(obj, "timed_ayahs_count", 0) or 0

    @staticmethod
    def resolve_timing_status(obj: object) -> TimingStatus:
        return timing_status(getattr(obj, "timed_ayahs_count", 0) or 0, getattr(obj, "ayahs_count", 0) or 0)
