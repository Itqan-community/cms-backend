from typing import Annotated

from django.db.models import F
from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.types import AbsoluteUrl

router = ItqanRouter(tags=[NinjaTag.RECITERS])


class ReciterOut(Schema):
    id: int
    name: str
    slug: str
    bio: str
    recitations_count: int = Field(0, description="Number of READY recitation assets for this reciter")
    image_url: AbsoluteUrl | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ReciterFilter(FilterSchema):
    name: Annotated[list[str] | None, FilterLookup(q="name__in")] = None
    name_ar: Annotated[list[str] | None, FilterLookup(q="name_ar__in")] = None
    slug: Annotated[list[str] | None, FilterLookup(q="slug__in")] = None


@router.get("reciters/", response=list[ReciterOut])
@paginate
@ordering(ordering_fields=["name", "name_ar", "name_en", "created_at", "updated_at"])
@searching(search_fields=["name", "name_en", "name_ar", "slug"])
def list_reciters(request: Request, filters: ReciterFilter = Query()):
    """
    Tenant Content API:

    List reciters that have at least one READY recitation Asset for this tenant/publisher.

    Conditions:
    - Reciter.is_active = True
    - Asset.category = RECITATION
    - Asset.resource.category = RECITATION
    - Asset.resource.status = READY
    - Asset owned by the tenant's publisher
    """
    repo = RecitationRepository()
    service = RecitationService(repo)

    publisher_q = request.publisher_q("assets__resource__publisher")
    qs = service.get_all_reciters(publisher_q, filters)

    return qs.order_by(F("name_ar").asc(nulls_last=True))
