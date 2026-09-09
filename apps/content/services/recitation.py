from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db.models import ProtectedError, Q, QuerySet
from django.utils.translation import gettext as _

from apps.content.models import LicenseChoice, Qiraah, Reciter, Riwayah
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.asset_access import guard_restrict_for_tenant
from apps.content.services.recitation_folder_resolution import find_folder_by_token
from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher

logger = logging.getLogger(__name__)

if TYPE_CHECKING:

    from apps.content.models import Asset, RecitationSurahTrack


class RecitationService:
    """Business layer for recitation reads/writes; owns validation and 404 semantics."""

    def __init__(self, repo: RecitationRepository | None = None) -> None:
        self.repo = repo or RecitationRepository()

    def get_all_recitations(
        self, publisher_q: Q | None = None, filters: Any = None, annotate_surahs_count: bool = False
    ) -> QuerySet[Asset]:
        """
        Business Logic: Retrieve all recitations with optional filtering.
        """
        filters_dict = filters.model_dump(exclude_none=True) if filters and hasattr(filters, "model_dump") else {}
        return self.repo.list_recitations_qs(publisher_q, filters_dict, annotate_surahs_count=annotate_surahs_count)

    def _get_recitation_or_404(self, recitation_slug: str, publisher_q: Q | None = None) -> Asset:
        """Fetch a READY recitation by slug or raise the canonical 404 error."""
        recitation = self.repo.get_recitation(recitation_slug, publisher_q=publisher_q)
        if recitation is None:
            raise ItqanError(
                error_name="recitation_not_found",
                message=_("Recitation with slug {slug} not found.").format(slug=recitation_slug),
                status_code=404,
            )
        return recitation

    def create_recitation(
        self,
        *,
        publisher_id: int,
        name_ar: str,
        name_en: str,
        description_ar: str,
        description_en: str,
        license: LicenseChoice,
        reciter_id: int,
        qiraah_id: int | None,
        riwayah_id: int | None,
        madd_level: Asset.MaddLevelChoice | None,
        meem_behaviour: Asset.MeemBehaviourChoice | None,
        year: int | None,
        is_open_access: bool = False,
        restricted_for_tenant: bool = False,
    ) -> Asset:
        """
        Business Logic: Create a new recitation.
        Validates publisher exists and computes base name/description.
        """
        # Trim all fields
        normalized_name_ar = (name_ar or "").strip()
        normalized_name_en = (name_en or "").strip()
        normalized_description_ar = (description_ar or "").strip()
        normalized_description_en = (description_en or "").strip()

        # Compute base name and description
        name = normalized_name_ar or normalized_name_en
        if not name:
            raise ItqanError(
                error_name="recitation_name_required",
                message=_("Recitation name (Arabic or English) is required."),
                status_code=400,
            )

        description = normalized_description_ar or normalized_description_en

        # Validate metadata existence and relationships
        self._validate_recitation_metadata(
            publisher_id=publisher_id,
            reciter_id=reciter_id,
            qiraah_id=qiraah_id,
            riwayah_id=riwayah_id,
        )

        recitation = self.repo.create_recitation(
            publisher_id=publisher_id,
            name=name,
            name_ar=normalized_name_ar,
            name_en=normalized_name_en,
            description=description,
            description_ar=normalized_description_ar,
            description_en=normalized_description_en,
            license=license,
            reciter_id=reciter_id,
            qiraah_id=qiraah_id,
            riwayah_id=riwayah_id,
            madd_level=madd_level,
            meem_behaviour=meem_behaviour,
            year=year,
            is_open_access=is_open_access,
            restricted_for_tenant=restricted_for_tenant,
        )
        logger.info(
            f"Recitation created [asset_id={recitation.pk}, publisher_id={publisher_id}, reciter_id={reciter_id}]"
        )
        return recitation

    def update_recitation(
        self,
        recitation_slug: str,
        fields: dict[str, Any],
        publisher_q: Q | None = None,
    ) -> Asset:
        """
        Business Logic: Update an existing recitation.
        """
        asset = self._get_recitation_or_404(recitation_slug, publisher_q=publisher_q)

        if fields.get("restricted_for_tenant") and not asset.restricted_for_tenant:
            guard_restrict_for_tenant(asset)

        # Trim input fields if present
        for field in ["name_ar", "name_en", "description_ar", "description_en"]:
            if field in fields:
                fields[field] = (fields[field] or "").strip()

        # Validate name fields if user is trying to update them
        if "name_ar" in fields or "name_en" in fields:
            final_name_ar = fields.get("name_ar") if "name_ar" in fields else getattr(asset, "name_ar", "")
            final_name_en = fields.get("name_en") if "name_en" in fields else getattr(asset, "name_en", "")

            if not final_name_ar and not final_name_en:
                raise ItqanError(
                    error_name="recitation_name_required",
                    message=_("Recitation name (Arabic or English) is required."),
                    status_code=400,
                )

        # Validate metadata if any ID is changing
        if any(f in fields for f in ["publisher_id", "reciter_id", "qiraah_id", "riwayah_id"]):
            self._validate_recitation_metadata(
                publisher_id=fields.get("publisher_id", asset.publisher_id),
                reciter_id=fields.get("reciter_id", asset.reciter_id),
                qiraah_id=fields.get("qiraah_id", asset.qiraah_id),
                riwayah_id=fields.get("riwayah_id", asset.riwayah_id),
            )

        updated = self.repo.update_recitation(asset, fields=fields)
        logger.info(f"Recitation updated [asset_id={updated.pk}, slug={recitation_slug}]")
        return updated

    def _validate_recitation_metadata(
        self,
        publisher_id: int,
        reciter_id: int,
        qiraah_id: int | None,
        riwayah_id: int | None,
    ) -> None:
        """
        Ensures all foreign keys exist and are consistent.
        """
        if not Publisher.objects.filter(id=publisher_id).exists():
            raise ItqanError(
                error_name="publisher_not_found",
                message=_("Publisher with id {id} not found.").format(id=publisher_id),
                status_code=404,
            )

        if not Reciter.objects.filter(id=reciter_id).exists():
            raise ItqanError(
                error_name="reciter_not_found",
                message=_("Reciter with id {id} not found.").format(id=reciter_id),
                status_code=404,
            )

        if qiraah_id and not Qiraah.objects.filter(id=qiraah_id).exists():
            raise ItqanError(
                error_name="qiraah_not_found",
                message=_("Qiraah with id {id} not found.").format(id=qiraah_id),
                status_code=404,
            )

        if riwayah_id and not Riwayah.objects.filter(id=riwayah_id).exists():
            raise ItqanError(
                error_name="riwayah_not_found",
                message=_("Riwayah with id {id} not found.").format(id=riwayah_id),
                status_code=404,
            )

    def delete_recitation(self, recitation_slug: str, publisher_q: Q | None = None) -> None:
        """
        Business Logic: Delete a recitation and its resource.
        """
        asset = self._get_recitation_or_404(recitation_slug, publisher_q=publisher_q)
        try:
            self.repo.delete_recitation(asset)
            logger.info(f"Recitation deleted [asset_id={asset.pk}, slug={recitation_slug}]")
        except ProtectedError as exc:
            raise ItqanError(
                error_name="related_objects_exist",
                message=str(_("Cannot delete Recitation because they are referenced through other objects")),
                status_code=400,
            ) from exc

    def get_asset_tracks(
        self,
        asset_id: int,
        publisher_q: Q,
        prefetch_timings: bool = False,
        folder: str | None = None,
        require_visible_folder: bool = False,
    ) -> QuerySet[RecitationSurahTrack]:
        """
        Business Logic: Retrieve tracks for a specific asset if it belongs to the publisher.

        Results are scoped to one folder (variant): the one identified by ``folder``,
        which accepts either the folder's slug or its name, or the asset's default
        folder when it is None. An unresolvable value raises ``folder_not_found``
        rather than returning an empty list, so callers can tell a typo apart from a
        folder that has no tracks yet.
        """
        folder_id = None
        if folder is not None:
            matched = find_folder_by_token(asset_id, folder, require_visible=require_visible_folder)
            if matched is None:
                raise ItqanError(
                    error_name="folder_not_found",
                    message=_("Folder {folder} not found.").format(folder=folder),
                    status_code=404,
                )
            folder_id = matched.id

        return self.repo.list_recitation_tracks_for_asset(
            asset_id,
            publisher_q=publisher_q,
            prefetch_timings=prefetch_timings,
            folder_id=folder_id,
        )

    def get_all_reciters(self, publisher_q: Q, filters: Any = None) -> QuerySet:
        """
        Business Logic: Retrieve all reciters that have READY recitations for a specific publisher/tenant.
        """
        filters_dict = filters.model_dump(exclude_none=True) if filters and hasattr(filters, "model_dump") else {}
        return self.repo.list_reciters_qs(publisher_q, filters_dict=filters_dict)

    def get_sample_recitation(self, publisher_q: Q | None = None) -> Asset | None:
        """
        Business Logic: First complete READY recitation for the public media-player
        sample endpoint (None when no qualifying recitation exists).
        """
        return self.repo.get_sample_asset(publisher_q)

    def get_sample_track(self, asset_id: int, surah_number: int) -> RecitationSurahTrack | None:
        """
        Business Logic: The default-folder track covering one surah of the
        sample recitation, with ayah timings prefetched in playback order.
        """
        return self.repo.get_default_track_for_surah(asset_id, surah_number)

    def get_range_segment(
        self,
        asset_id: int,
        surah_number: int,
        from_ayah: int,
        to_ayah: int,
        folder: str | None = None,
        require_visible_folder: bool = True,
    ) -> tuple[RecitationSurahTrack, Any, list[Any], int, int]:
        # Resolve and validate one contiguous ayah range within a single surah.
        # Returns (track, folder, timings_subset, start_ms, end_ms) where the
        # subset covers every ayah in [from_ayah, to_ayah] in playback order.
        # Range problems (order, bounds, gaps) raise 422 validation_error so
        # clients can tell bad input apart from a missing track (404).
        from apps.core.mixins.constants import QURAN_SURAHS

        if surah_number not in QURAN_SURAHS:
            raise ItqanError(
                error_name="validation_error",
                message=_("Surah {surah} is out of range (1-114).").format(surah=surah_number),
                status_code=422,
            )
        if from_ayah > to_ayah:
            raise ItqanError(
                error_name="validation_error",
                message=_("Invalid ayah range: from ({from_ayah}) must not exceed to ({to_ayah}).").format(
                    from_ayah=from_ayah, to_ayah=to_ayah
                ),
                status_code=422,
            )
        ayahs_count = QURAN_SURAHS[surah_number]["ayahs_count"]
        if from_ayah < 1 or to_ayah > ayahs_count:
            raise ItqanError(
                error_name="validation_error",
                message=_("Ayah range {from_ayah}-{to_ayah} is outside surah {surah} (1-{max}).").format(
                    from_ayah=from_ayah, to_ayah=to_ayah, surah=surah_number, max=ayahs_count
                ),
                status_code=422,
            )

        folder_id = None
        matched_folder = None
        if folder is not None:
            matched_folder = find_folder_by_token(asset_id, folder, require_visible=require_visible_folder)
            if matched_folder is None:
                raise ItqanError(
                    error_name="folder_not_found",
                    message=_("Folder {folder} not found.").format(folder=folder),
                    status_code=404,
                )
            folder_id = matched_folder.id

        track = self.repo.get_single_track(asset_id, surah_number, folder_id=folder_id)
        if track is None:
            raise ItqanError(
                error_name="not_found",
                message=_("No track for surah {surah} on this recitation.").format(surah=surah_number),
                status_code=404,
            )
        if matched_folder is None:
            matched_folder = track.folder

        by_ayah = {t.ayah_key: t for t in track.ayah_timings.all()}
        subset = []
        for ayah_number in range(from_ayah, to_ayah + 1):
            timing = by_ayah.get(f"{surah_number}:{ayah_number}")
            if timing is None:
                raise ItqanError(
                    error_name="validation_error",
                    message=_("Ayah {surah}:{ayah} has no timing on this track.").format(
                        surah=surah_number, ayah=ayah_number
                    ),
                    status_code=422,
                )
            subset.append(timing)

        start_ms = subset[0].start_ms
        end_ms = subset[-1].end_ms
        if end_ms <= start_ms:
            raise ItqanError(
                error_name="validation_error",
                message=_("Ayah range {from_ayah}-{to_ayah} has invalid timings.").format(
                    from_ayah=from_ayah, to_ayah=to_ayah
                ),
                status_code=422,
            )
        return track, matched_folder, subset, start_ms, end_ms
