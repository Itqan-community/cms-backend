import datetime

from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Reciter
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITERS])


class ReciterOut(Schema):
    id: int
    identifier: str
    name_ar: str | None = None
    name_en: str | None = None
    nationality: str
    date_of_birth: datetime.date | None = None
    date_of_death: datetime.date | None = None
    about: str


class CreateReciterIn(Schema):
    identifier: str = Field(..., min_length=1)
    name_ar: str = Field(..., min_length=1)
    name_en: str = Field(..., min_length=1)
    nationality: str
    date_of_birth: datetime.date | None = None
    date_of_death: datetime.date | None = None
    about: str | None = None


@router.get("reciters/", response=list[ReciterOut], auth=None)
@paginate
@ordering(ordering_fields=["name_ar", "name_en", "identifier", "nationality"])
@searching(search_fields=["identifier", "name_ar", "name_en", "nationality"])
def list_reciters(request: Request):
    return Reciter.objects.filter(is_active=True)


@router.post("reciters/", response=ReciterOut)
def create_reciter(request: Request, data: CreateReciterIn):
    reciter = Reciter.objects.create(
        identifier=data.identifier,
        name=data.name_ar,
        name_ar=data.name_ar,
        name_en=data.name_en,
        nationality=data.nationality,
        date_of_birth=data.date_of_birth,
        date_of_death=data.date_of_death,
        about=data.about or "",
    )
    return reciter
