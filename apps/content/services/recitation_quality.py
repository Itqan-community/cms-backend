from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.content.cache import invalidate_recitation_quality_cache
from apps.content.models import RecitationQuality
from apps.content.repositories.recitation_quality import RecitationQualityRepository
from apps.core.audit import update_with_history
from apps.core.ninja_utils.errors import ItqanError

if TYPE_CHECKING:
    from django.db.models import QuerySet

logger = logging.getLogger(__name__)


class RecitationQualityService:
    def __init__(self, repo: RecitationQualityRepository | None = None) -> None:
        self.repo = repo or RecitationQualityRepository()

    def list_qualities(self, asset_id: int, annotate_tracks_count: bool = False) -> QuerySet[RecitationQuality]:
        """Business Logic: list an asset's qualities."""
        return self.repo.list_for_asset(asset_id, annotate_tracks_count=annotate_tracks_count)

    def get_quality_or_404(self, asset_id: int, quality_slug: str, publisher_q: Q | None = None) -> RecitationQuality:
        """Business Logic: resolve a quality by slug, raising a typed 404 when absent."""
        quality = self.repo.get_by_slug(asset_id, quality_slug, publisher_q=publisher_q)
        if quality is None:
            raise ItqanError(
                error_name="quality_not_found",
                message=_("Quality with slug {slug} not found.").format(slug=quality_slug),
                status_code=404,
            )
        return quality

    def resolve_quality(
        self, asset_id: int, quality_slug: str | None, publisher_q: Q | None = None
    ) -> RecitationQuality:
        """
        Business Logic: resolve the quality a request is asking for.

        An explicit slug must exist (404 otherwise). Without one, the asset's
        default quality is served, which is what keeps pre-quality API callers working.
        """
        if quality_slug is not None:
            return self.get_quality_or_404(asset_id, quality_slug, publisher_q=publisher_q)

        default_quality = self.repo.get_default_for_asset(asset_id)
        if default_quality is None:
            # Every recitation gets a default quality at creation, and existing ones
            # were backfilled, so this means the asset was built outside the service
            # layer. Surface it rather than silently returning no tracks.
            logger.error(f"Recitation asset has no default quality [asset_id={asset_id}]")
            raise ItqanError(
                error_name="quality_not_found",
                message=_("This recitation has no default quality."),
                status_code=404,
            )
        return default_quality

    def create_quality(
        self,
        *,
        asset_id: int,
        name_ar: str,
        name_en: str,
    ) -> RecitationQuality:
        """Business Logic: add a variant quality to a recitation."""
        normalized_name_ar = (name_ar or "").strip()
        normalized_name_en = (name_en or "").strip()

        name = normalized_name_ar or normalized_name_en
        if not name:
            raise ItqanError(
                error_name="quality_name_required",
                message=_("Quality name (Arabic or English) is required."),
                status_code=400,
            )

        quality = self.repo.create_quality(
            asset_id=asset_id,
            name=name,
            name_ar=normalized_name_ar,
            name_en=normalized_name_en,
            is_default=False,
        )
        logger.info(f"Recitation quality created [quality_id={quality.pk}, asset_id={asset_id}, slug={quality.slug}]")
        return quality

    def update_quality(
        self,
        *,
        asset_id: int,
        quality_slug: str,
        fields: dict[str, Any],
        publisher_q: Q | None = None,
    ) -> RecitationQuality:
        """
        Business Logic: update a quality's names, visibility, or default status.

        The slug is left alone on rename: it is the public ``?quality=`` value, and
        changing it would break links and cached responses already pointing at it.
        """
        quality = self.get_quality_or_404(asset_id, quality_slug, publisher_q=publisher_q)

        if "is_default" in fields:
            is_default = fields.pop("is_default")
            if is_default is False:
                raise ItqanError(
                    error_name="cannot_unset_default_quality",
                    message=_("Use another quality's set-default action instead of clearing the default flag."),
                    status_code=400,
                )
            if is_default is True:
                return self._promote_to_default(quality)

        visibility_changed = False
        if "is_visible" in fields:
            is_visible = fields.pop("is_visible")
            if is_visible is False and quality.is_default:
                raise ItqanError(
                    error_name="cannot_hide_default_quality",
                    message=_("The default quality cannot be hidden."),
                    status_code=400,
                )
            if is_visible is not None and is_visible != quality.is_visible:
                quality.is_visible = is_visible
                visibility_changed = True
                logger.info(f"Recitation quality visibility changed [quality_id={quality.pk}, is_visible={is_visible}]")

        name_fields = {k: v for k, v in fields.items() if k in ("name_ar", "name_en")}
        if name_fields:
            for field in ("name_ar", "name_en"):
                if field in name_fields:
                    name_fields[field] = (name_fields[field] or "").strip()

            final_name_ar = name_fields.get("name_ar", quality.name_ar) or ""
            final_name_en = name_fields.get("name_en", quality.name_en) or ""
            if not final_name_ar and not final_name_en:
                raise ItqanError(
                    error_name="quality_name_required",
                    message=_("Quality name (Arabic or English) is required."),
                    status_code=400,
                )

            ordered_fields: dict[str, str | None] = {"name": final_name_ar or final_name_en}
            ordered_fields.update(name_fields)
            quality = self.repo.update_quality(quality, fields=ordered_fields)
        elif visibility_changed:
            quality.save(update_fields=["is_visible", "updated_at"])

        if visibility_changed:
            invalidate_recitation_quality_cache(asset_id, quality)

        if name_fields or visibility_changed:
            logger.info(f"Recitation quality updated [quality_id={quality.pk}, asset_id={asset_id}]")
        return quality

    def _promote_to_default(self, quality: RecitationQuality) -> RecitationQuality:
        if quality.is_default:
            return quality

        if not quality.is_visible:
            raise ItqanError(
                error_name="cannot_set_hidden_quality_as_default",
                message=_("A hidden quality cannot be set as the default."),
                status_code=400,
            )

        with transaction.atomic():
            update_with_history(
                RecitationQuality.objects.filter(asset_id=quality.asset_id, is_default=True),
                is_default=False,
            )
            quality.is_default = True
            quality.save(update_fields=["is_default", "updated_at"])

        logger.info(
            f"Recitation quality promoted to default [quality_id={quality.pk}, asset_id={quality.asset_id}, slug={quality.slug}]"
        )
        invalidate_recitation_quality_cache(quality.asset_id, quality)
        return quality

    def delete_quality(self, *, asset_id: int, quality_slug: str, publisher_q: Q | None = None) -> None:
        """
        Business Logic: delete a variant quality and everything inside it.

        The default quality is protected: it is what the APIs fall back to when no
        quality is named, so removing it would break every caller of this recitation.
        """
        quality = self.get_quality_or_404(asset_id, quality_slug, publisher_q=publisher_q)

        if quality.is_default:
            raise ItqanError(
                error_name="cannot_delete_default_quality",
                message=_("The default quality cannot be deleted."),
                status_code=400,
            )

        asset_id = quality.asset_id
        self.repo.delete_quality(quality)
        invalidate_recitation_quality_cache(asset_id, quality)
        logger.info(f"Recitation quality deleted [asset_id={asset_id}, slug={quality_slug}]")
