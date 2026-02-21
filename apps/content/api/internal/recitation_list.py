from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Asset
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RecitationReciterOut(Schema):
    id: int
    name: str


class RecitationRiwayahOut(Schema):
    id: int
    name: str


class RecitationQiraahOut(Schema):
    id: int
    name: str


class RecitationListOut(Schema):
    id: int
    name: str
    description: str
    madd_level: Asset.MaddLevelChoice | None
    meem_behaviour: Asset.MeemBehaviorChoice | None
    year: int | None
    reciter: RecitationReciterOut
    riwayah: RecitationRiwayahOut | None
    qiraah: RecitationQiraahOut | None


class RecitationFilter(FilterSchema):
    publisher_id: list[int] | None = Field(None, q="resource__publisher_id__in")
    reciter_id: list[int] | None = Field(None, q="reciter_id__in")
    riwayah_id: list[int] | None = Field(
        None,
        q="riwayah_id__in",
        description="Filter by Riwayah (e.g. عاصم عن حفص). Combined with qiraah_id, results are narrowed by both conditions (AND semantics).",
    )
    qiraah_id: list[int] | None = Field(
        None,
        q="qiraah_id__in",
        description="Filter by Recitation Type / Qiraah (e.g. Hafs, Warsh).",
    )


@router.get("recitations/", response=list[RecitationListOut])
@paginate
@ordering(ordering_fields=["name", "created_at", "updated_at"])
@searching(
    search_fields=[
        "name",
        "name_ar",
        "description",
        "description_ar",
        "resource__publisher__name",
        "resource__publisher__name_ar",
        "reciter__name",
        "reciter__name_ar",
    ]
)
def list_recitations(request: Request, filters: RecitationFilter = Query()):
    """
    List recitations with support for:
    - **Full-text search** by reciter name (Arabic & English), asset name, description, publisher name.
    - **Filter by Recitation Type / Qiraah** (`qiraah_id`): e.g. Hafs, Warsh.
    - **Filter by Riwayah** (`riwayah_id`): e.g. عاصم عن حفص.
    - **Filter by Reciter** (`reciter_id`).
    - **Filter by Publisher** (`publisher_id`).
    - **Server-side pagination** via `page` & `page_size` query parameters.
    - **Ordering** via `ordering` query parameter (name, -name, created_at, -created_at, etc.).
    """
    repo = RecitationRepository()
    service = RecitationService(repo)

    publisher_q = request.publisher_q("resource__publisher")
    qs = service.get_all_recitations(publisher_q, filters)

    return qs
