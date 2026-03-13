from ninja import Schema
from pydantic import AwareDatetime

from apps.content.repositories.reciter import ReciterRepository
from apps.content.services.reciter_portal import ReciterPortalService
from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITERS])


class ReciterCreateIn(Schema):
    name: str
    name_ar: str = ""
    name_en: str = ""
    bio: str = ""
    bio_ar: str = ""
    bio_en: str = ""
    is_active: bool = True


class ReciterCreateOut(Schema):
    id: int
    name: str
    slug: str
    name_ar: str | None
    name_en: str | None
    bio: str
    bio_ar: str | None
    bio_en: str | None
    is_active: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime


@router.post(
    "reciters/",
    response={201: ReciterCreateOut, 400: NinjaErrorResponse},
    auth=ninja_jwt_auth,
)
def create_reciter(request: Request, data: ReciterCreateIn) -> tuple[int, object]:
    service = ReciterPortalService(ReciterRepository())
    reciter = service.create_reciter(
        name=data.name,
        name_ar=data.name_ar,
        name_en=data.name_en,
        bio=data.bio,
        bio_ar=data.bio_ar,
        bio_en=data.bio_en,
        is_active=data.is_active,
    )
    return 201, reciter
