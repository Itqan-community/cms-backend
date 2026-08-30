from __future__ import annotations

import json
import logging

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.content.api.public.recitation_track_list import RecitationAyahTimingOut, RecitationSurahTrackOut
from apps.content.models import Asset, AssetVersion, RecitationFolder, RecitationSurahTrack
from apps.core.mixins.constants import QURAN_SURAHS
from config.settings.base import CLOUDFLARE_R2_PUBLIC_BASE_URL

logger = logging.getLogger(__name__)


def _build_recitations_json(asset: Asset, folder: RecitationFolder) -> tuple[str, str]:
    tracks = (
        RecitationSurahTrack.objects.filter(asset=asset, folder=folder)
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
    # The folder slug is part of the filename so variants (clear, with-echo, ...)
    # each get their own export instead of overwriting one another.
    parts = [f"asset_{asset.id}"]
    if reciter_slug:
        parts.append(reciter_slug)
    parts.append(folder.slug)
    filename = "_".join(parts) + "_recitations.json"
    return payload, filename


def sync_asset_recitations_json_file(asset_id: int, folder_id: int | None = None) -> tuple[AssetVersion, str]:
    """
    Build the recitation JSON for one folder of the Asset and save it to an AssetVersion.

    Each folder (variant) gets its own AssetVersion, named after the folder slug, because
    echo/delay variants have genuinely different ayah offsets and must not overwrite each
    other's export. ``folder_id`` defaults to the asset's default folder.

    - Raises ValueError if the Asset or the folder does not exist.
    - Returns (asset_version, filename) on success.
    """
    logger.info(f"Recitation JSON sync started [asset_id={asset_id}, folder_id={folder_id}]")

    asset: Asset | None = Asset.objects.filter(pk=asset_id).first()
    if not asset:
        raise ValueError(_("Asset {asset_id} not found").format(asset_id=asset_id))

    if folder_id is not None:
        folder: RecitationFolder | None = RecitationFolder.objects.filter(pk=folder_id, asset_id=asset_id).first()
    else:
        folder = RecitationFolder.objects.filter(asset_id=asset_id, is_default=True).first()

    if not folder:
        raise ValueError(
            _("Folder {folder_id} not found for asset {asset_id}").format(folder_id=folder_id, asset_id=asset_id)
        )

    # One version per folder, identified by the folder slug. Looking it up by name
    # keeps repeated syncs of the same variant updating a single row.
    version_name = folder.slug
    version: AssetVersion | None = AssetVersion.objects.filter(asset=asset, name=version_name).first()
    if not version:
        version = AssetVersion.objects.create(asset=asset, name=version_name)

    payload, filename = _build_recitations_json(asset, folder)
    payload_bytes = payload.encode("utf-8")
    track_count = payload.count('"surah_number"')

    # Atomic write to this folder's version file
    with transaction.atomic():
        content = ContentFile(payload_bytes)
        version.file_url.save(filename, content, save=False)
        version.size_bytes = len(payload_bytes)
        version.save(update_fields=["file_url", "size_bytes", "updated_at"])

    logger.info(
        f"Recitation JSON sync complete [asset_id={asset_id}, folder_id={folder.pk}, version_id={version.pk}, "
        f"tracks={track_count}, size_bytes={len(payload_bytes)}, filename={filename}]"
    )
    return version, filename
