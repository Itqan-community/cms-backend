from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db.models import ProtectedError, Q, QuerySet
from django.utils.translation import gettext as _

from apps.content.models import LicenseChoice, Qiraah, Reciter, Riwayah
from apps.content.repositories.recitation import RecitationRepository
from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher

logger = logging.getLogger(__name__)

if TYPE_CHECKING:

    from apps.content.models import Asset, RecitationSurahTrack


class RecitationService:
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

    def _get_recitation_or_404(self, recitation_slug: str) -> Asset:
        recitation = self.repo.get_recitation(recitation_slug)
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
        )
        logger.info(
            f"Recitation created [asset_id={recitation.pk}, publisher_id={publisher_id}, reciter_id={reciter_id}]"
        )
        return recitation

    def update_recitation(
        self,
        recitation_slug: str,
        fields: dict[str, Any],
    ) -> Asset:
        """
        Business Logic: Update an existing recitation.
        """
        asset = self._get_recitation_or_404(recitation_slug)

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

    def delete_recitation(self, recitation_slug: str) -> None:
        """
        Business Logic: Delete a recitation and its resource.
        """
        asset = self._get_recitation_or_404(recitation_slug)
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
        self, asset_id: int, publisher_q: Q, prefetch_timings: bool = False
    ) -> QuerySet[RecitationSurahTrack]:
        """
        Business Logic: Retrieve tracks for a specific asset if it belongs to the publisher.
        """
        return self.repo.list_recitation_tracks_for_asset(
            asset_id, publisher_q=publisher_q, prefetch_timings=prefetch_timings
        )

    def get_all_reciters(self, publisher_q: Q, filters: Any = None) -> QuerySet:
        """
        Business Logic: Retrieve all reciters that have READY recitations for a specific publisher/tenant.
        """
        filters_dict = filters.model_dump(exclude_none=True) if filters and hasattr(filters, "model_dump") else {}
        return self.repo.list_reciters_qs(publisher_q, filters_dict=filters_dict)
