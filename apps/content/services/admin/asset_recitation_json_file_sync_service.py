from __future__ import annotations

import json

from django.core.files.base import ContentFile
from django.db import transaction

from apps.content.api.public.recitation_detail import (
    RecitationAyahTimingOut,
    RecitationSurahTrackOut,
)
from apps.content.models import Asset, AssetVersion, RecitationSurahTrack
from apps.core.mixins.constants import QURAN_SURAHS
from config.settings.base import CLOUDFLARE_R2_PUBLIC_BASE_URL


def _build_recitations_json(asset: Asset) -> tuple[str, str]:
    tracks = (
        RecitationSurahTrack.objects.filter(asset=asset)
        .prefetch_related("ayah_timings")
        .order_by("surah_number")
        .only("surah_number", "audio_file", "duration_ms", "size_bytes")
    )

    result: list[RecitationSurahTrackOut] = []
    for track in tracks:
        url = f"{CLOUDFLARE_R2_PUBLIC_BASE_URL}/media/{track.audio_file.name}"
        sorted_ayah_timings_qs = sorted(
            track.ayah_timings.all(),
            key=lambda a: (int(a.ayah_key.split(":")[0]), int(a.ayah_key.split(":")[1])),
        )
        ayahs_timings = [
            RecitationAyahTimingOut(
                ayah_key=t.ayah_key,
                start_ms=t.start_ms,
                end_ms=t.end_ms,
                duration_ms=t.duration_ms,
            )
            for t in sorted_ayah_timings_qs
        ]
        result.append(
            RecitationSurahTrackOut(
                surah_number=track.surah_number,
                surah_name=QURAN_SURAHS[track.surah_number]["name"],
                surah_name_en=QURAN_SURAHS[track.surah_number]["name_en"],
                audio_url=url,
                duration_ms=track.duration_ms,
                size_bytes=track.size_bytes,
                revelation_order=QURAN_SURAHS[track.surah_number]["revelation_order"],
                revelation_place=QURAN_SURAHS[track.surah_number]["revelation_place"],
                ayahs_count=QURAN_SURAHS[track.surah_number]["ayahs_count"],
                ayahs_timings=ayahs_timings,
            )
        )

    payload = json.dumps([i.model_dump() for i in result], ensure_ascii=False, indent=2)
    reciter_slug = asset.reciter.slug if getattr(asset, "reciter", None) else ""
    filename = (
        f"asset_{asset.id}_{reciter_slug}_recitations.json" if reciter_slug else f"asset_{asset.id}_recitations.json"
    )
    return payload, filename


def sync_asset_recitations_json_file(asset_id: int) -> tuple[AssetVersion, str]:
    """
    Build the recitation JSON for the Asset and save it into the LATEST AssetVersion.file_url.
    - Raises ValueError if the Asset does not exist or if there is no latest AssetVersion.
    - Returns (updated_asset_version, filename) on success.
    """
    asset: Asset | None = Asset.objects.filter(pk=asset_id).first()
    if not asset:
        raise ValueError(f"Asset {asset_id} not found")

    latest_version: AssetVersion | None = asset.get_latest_version()
    if not latest_version:
        raise ValueError(f"Asset {asset_id} has no latest AssetVersion to update")

    payload, filename = _build_recitations_json(asset)
    payload_bytes = payload.encode("utf-8")

    # Atomic write to the latest version file
    with transaction.atomic():
        content = ContentFile(payload_bytes)
        latest_version.file_url.save(filename, content, save=False)
        latest_version.size_bytes = len(payload_bytes)
        latest_version.save(update_fields=["file_url", "size_bytes", "updated_at"])

    return latest_version, filename
