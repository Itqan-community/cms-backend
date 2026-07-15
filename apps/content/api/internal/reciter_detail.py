import datetime
from typing import Literal

from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _
from ninja import Field, Schema
from pydantic import AwareDatetime

from apps.content.models import CategoryChoice, Reciter, StatusChoice
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.types import AbsoluteUrl

router = ItqanRouter(tags=[NinjaTag.RECITERS])


class ReciterDetailOut(Schema):
    id: int
    name_ar: str | None
    name_en: str | None
    bio_ar: str | None
    bio_en: str | None
    recitations_count: int = Field(0, description="Number of READY recitation assets for this reciter")
    nationality: str | None = Field(None, description="2-letter ISO country code")
    slug: str
    image_url: AbsoluteUrl | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    date_of_death: datetime.date | None = None

    @staticmethod
    def resolve_nationality(obj: Reciter) -> str | None:
        if obj.nationality and hasattr(obj.nationality, "code"):
            return obj.nationality.code
        return obj.nationality if isinstance(obj.nationality, str) else None


@router.get(
    "reciters/{reciter_slug}/",
    response={
        200: ReciterDetailOut,
        404: NinjaErrorResponse[Literal["reciter_not_found"]],
    },
    auth=None,
)
def get_reciter(request: Request, reciter_slug: str):
    try:
        return Reciter.objects.annotate(
            recitations_count=Count(
                "assets",
                filter=Q(assets__category=CategoryChoice.RECITATION, assets__status=StatusChoice.READY),
                distinct=True,
            )
        ).get(slug=reciter_slug, is_active=True)
    except Reciter.DoesNotExist as exc:
        raise ItqanError(
            error_name="reciter_not_found",
            message=_("Reciter with slug {slug} not found.").format(slug=reciter_slug),
            status_code=404,
        ) from exc
