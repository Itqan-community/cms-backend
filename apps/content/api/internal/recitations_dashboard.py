"""
Dashboard statistics endpoint for the Quranic Audio Library.

GET /cms-api/dashboard/recitations/
Returns aggregate statistics matching the frontend dashboard UI:
- total_reciters (قارئ متاح)
- total_qiraahs (قراءة متاحة)
- total_riwayahs (رواية متاحة)
- total_recitations
- total_tracks
- file_format (تنسيق الملفات)
- recitations_per_riwayah
- recitations_per_type
"""

from django.db.models import Count, Q

from ninja import Schema

from apps.content.models import Asset, RecitationSurahTrack, Reciter, Resource, Riwayah, Qiraah
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


# ── Response Schemas ────────────────────────────────────────────────


class RiwayahStatOut(Schema):
    """Recitation count per Riwayah."""

    riwayah_id: int
    riwayah_name: str
    count: int


class TypeStatOut(Schema):
    """Recitation count per recitation type (murattal, mujawwad, etc.)."""

    recitation_type: str | None
    count: int


class RecitationsDashboardOut(Schema):
    """Aggregate statistics for the recitations dashboard — matches frontend UI."""

    total_reciters: int
    total_qiraahs: int
    total_riwayahs: int
    total_recitations: int
    total_tracks: int
    file_format: str
    recitations_per_riwayah: list[RiwayahStatOut]
    recitations_per_type: list[TypeStatOut]


# ── Endpoint ────────────────────────────────────────────────────────


@router.get("dashboard/recitations/", response=RecitationsDashboardOut)
def recitations_dashboard(request: Request):
    """
    Returns high-level statistics for the Quranic Audio Library dashboard.

    All counts are scoped to the current publisher/tenant and only include
    READY recitation resources.
    """
    publisher_q = request.publisher_q("resource__publisher")

    # Base filter: only READY recitation assets for this publisher
    base_filter = Q(
        category=Resource.CategoryChoice.RECITATION,
        resource__category=Resource.CategoryChoice.RECITATION,
        resource__status=Resource.StatusChoice.READY,
    ) & publisher_q

    # ── Total counts ────────────────────────────────────────────
    total_recitations = Asset.objects.filter(base_filter).count()

    # Reciters with at least one READY recitation
    reciter_publisher_q = request.publisher_q("assets__resource__publisher")
    total_reciters = (
        Reciter.objects.filter(
            is_active=True,
            assets__category=Resource.CategoryChoice.RECITATION,
            assets__resource__category=Resource.CategoryChoice.RECITATION,
            assets__resource__status=Resource.StatusChoice.READY,
        )
        .filter(reciter_publisher_q)
        .distinct()
        .count()
    )

    # Qiraahs with at least one READY recitation
    qiraah_publisher_q = request.publisher_q("riwayahs__assets__resource__publisher")
    total_qiraahs = (
        Qiraah.objects.filter(
            is_active=True,
            riwayahs__is_active=True,
            riwayahs__assets__category=Resource.CategoryChoice.RECITATION,
            riwayahs__assets__resource__category=Resource.CategoryChoice.RECITATION,
            riwayahs__assets__resource__status=Resource.StatusChoice.READY,
        )
        .filter(qiraah_publisher_q)
        .distinct()
        .count()
    )

    # Riwayahs with at least one READY recitation
    riwayah_publisher_q = request.publisher_q("assets__resource__publisher")
    total_riwayahs = (
        Riwayah.objects.filter(
            is_active=True,
            assets__category=Resource.CategoryChoice.RECITATION,
            assets__resource__category=Resource.CategoryChoice.RECITATION,
            assets__resource__status=Resource.StatusChoice.READY,
        )
        .filter(riwayah_publisher_q)
        .distinct()
        .count()
    )

    # Total tracks
    track_publisher_q = request.publisher_q("asset__resource__publisher")
    total_tracks = (
        RecitationSurahTrack.objects.filter(
            asset__category=Resource.CategoryChoice.RECITATION,
            asset__resource__category=Resource.CategoryChoice.RECITATION,
            asset__resource__status=Resource.StatusChoice.READY,
        )
        .filter(track_publisher_q)
        .count()
    )

    # ── Recitations per Riwayah ─────────────────────────────────
    per_riwayah_qs = (
        Riwayah.objects.filter(
            is_active=True,
            assets__category=Resource.CategoryChoice.RECITATION,
            assets__resource__category=Resource.CategoryChoice.RECITATION,
            assets__resource__status=Resource.StatusChoice.READY,
        )
        .filter(riwayah_publisher_q)
        .annotate(
            count=Count(
                "assets",
                filter=Q(
                    assets__category=Resource.CategoryChoice.RECITATION,
                    assets__resource__category=Resource.CategoryChoice.RECITATION,
                    assets__resource__status=Resource.StatusChoice.READY,
                )
                & riwayah_publisher_q,
            )
        )
        .values("id", "name", "count")
        .order_by("-count")
    )

    recitations_per_riwayah = [
        RiwayahStatOut(
            riwayah_id=row["id"],
            riwayah_name=row["name"],
            count=row["count"],
        )
        for row in per_riwayah_qs
    ]

    # ── Recitations per type (recitation_type) ──────────────────
    per_type_qs = (
        Asset.objects.filter(base_filter)
        .values("recitation_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    recitations_per_type = [
        TypeStatOut(
            recitation_type=row["recitation_type"],
            count=row["count"],
        )
        for row in per_type_qs
    ]

    # File format — always MP3 for audio recitations
    file_format = "MP3"

    return RecitationsDashboardOut(
        total_reciters=total_reciters,
        total_qiraahs=total_qiraahs,
        total_riwayahs=total_riwayahs,
        total_recitations=total_recitations,
        total_tracks=total_tracks,
        file_format=file_format,
        recitations_per_riwayah=recitations_per_riwayah,
        recitations_per_type=recitations_per_type,
    )
