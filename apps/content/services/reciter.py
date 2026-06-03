from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any

from django.db import IntegrityError
from django.db.models import ProtectedError
from django.utils.translation import gettext as _

from apps.content.models import Reciter as ReciterModel
from apps.content.repositories.reciter import ReciterRepository
from apps.core.ninja_utils.errors import ItqanError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:

    from apps.content.models import Reciter


class ReciterService:
    def __init__(self, repo: ReciterRepository | None = None) -> None:
        self.repo = repo or ReciterRepository()

    def _get_reciter_or_404(self, reciter_slug: str) -> Reciter:
        try:
            return ReciterModel.objects.get(slug=reciter_slug)
        except ReciterModel.DoesNotExist as exc:
            raise ItqanError(
                error_name="reciter_not_found",
                message=_("Reciter with slug {slug} not found.").format(slug=reciter_slug),
                status_code=404,
            ) from exc

    def create_reciter(
        self,
        *,
        name_ar: str | None,
        name_en: str | None,
        bio_ar: str = "",
        bio_en: str = "",
        nationality: str = "",
        date_of_death: datetime.date | None = None,
        image_url: Any = None,
    ) -> Reciter:
        """
        Business Logic: Create a new reciter.
        Validates names.
        """
        normalized_name_ar = (name_ar or "").strip()
        normalized_name_en = (name_en or "").strip()
        name = normalized_name_ar or normalized_name_en

        if not name:
            raise ItqanError(
                error_name="reciter_name_required",
                message=_("Reciter name (Arabic or English) is required."),
                status_code=400,
            )

        try:
            kwargs = {
                "name": name,
                "name_ar": normalized_name_ar,
                "name_en": normalized_name_en,
                "bio_ar": bio_ar,
                "bio_en": bio_en,
                "nationality": nationality,
                "date_of_death": date_of_death,
            }
            if image_url is not None:
                kwargs["image_url"] = image_url

            reciter = self.repo.create_reciter(**kwargs)
            logger.info(f"Reciter created [reciter_id={reciter.pk}, name={reciter.name!r}]")
            return reciter
        except IntegrityError as err:
            raise ItqanError(
                error_name="reciter_already_exists",
                message=_("A reciter with this name already exists."),
                status_code=409,
            ) from err

    def update_reciter(
        self,
        reciter_slug: str,
        fields: dict[str, Any],
    ) -> Reciter:
        """
        Business Logic: Update an existing reciter.
        Validates name requirement.
        """
        reciter = self._get_reciter_or_404(reciter_slug)

        if "name_ar" in fields or "name_en" in fields:
            new_name_ar = fields.get("name_ar", getattr(reciter, "name_ar", ""))
            new_name_en = fields.get("name_en", getattr(reciter, "name_en", ""))

            final_name_ar = (new_name_ar or "").strip()
            final_name_en = (new_name_en or "").strip()

            if not final_name_ar and not final_name_en:
                raise ItqanError(
                    error_name="reciter_name_required",
                    message=_("Reciter name (Arabic or English) is required."),
                    status_code=400,
                )
            fields["name_ar"] = final_name_ar
            fields["name_en"] = final_name_en

        try:
            updated = self.repo.update_reciter(reciter, fields=fields)
            logger.info(f"Reciter updated [reciter_id={updated.pk}, slug={reciter_slug}]")
            return updated
        except IntegrityError as err:
            raise ItqanError(
                error_name="reciter_already_exists",
                message=_("A reciter with this name already exists."),
                status_code=409,
            ) from err

    def delete_reciter(self, reciter_slug: str) -> None:
        """
        Business Logic: Delete a reciter.
        """
        reciter = self._get_reciter_or_404(reciter_slug)
        try:
            self.repo.delete_reciter(reciter)
            logger.info(f"Reciter deleted [reciter_id={reciter.pk}, slug={reciter_slug}]")
        except ProtectedError as exc:
            raise ItqanError(
                error_name="related_objects_exist",
                message=str(_("Cannot delete Reciter because they are referenced through other objects")),
                status_code=400,
            ) from exc
