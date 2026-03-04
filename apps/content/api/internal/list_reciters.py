from ninja import Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.core.ninja_utils.types import AbsoluteUrl
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService






router = ItqanRouter(tags=[NinjaTag.RECITERS])

class ReciterListOut(Schema):
    id: int
    name: str
    slug: str
    bio: str
    is_active: bool
    image_url: AbsoluteUrl | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


@router.get("reciters/", response=list[ReciterListOut])
@paginate
@ordering(ordering_fields=["name_ar", "name_en", "created_at", "updated_at"])
@searching(search_fields=["name_en", "name_ar", "slug"])
def list_reciters(request: Request):

    recitation_repo     = RecitationRepository()
    recitation_service  = RecitationService(recitation_repo)
    publisher_q         = request.publisher_q("assets__resource__publisher")
    qs                  = recitation_service.get_all_reciters(publisher_q)

    return qs.order_by("name_ar") #default ordering by name_ar if there is no ordering query param
