from datetime import date

from django.db.models import Count, Q
from ninja import File, FilterSchema, Query, Schema, files, Form
from ninja.pagination import paginate
from pydantic import Field
from apps.core.ninja_utils.errors import ItqanError

from apps.content.models import Reciter
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITERS])


class ReciterOut(Schema):
    id: int
    name: str
    recitations_count: int = Field(0, description="Number of READY recitation assets for this reciter")

class ReciterCreateIn(Schema):
    name: str = Form(...)
    nationality: str = Form(...)
    date_of_birth: date = Form(...)
    date_of_death: date | None = Form(None)
    slug: str | None = Form(None)
    is_active: bool = Form(True)
    bio: str | None = Form(None)
    reciter_identifier: str = Form(...)

@router.post("reciters/", response=ReciterOut)
def create_reciter(
    request: Request,
    data: ReciterCreateIn = Form(...),
    image: files.UploadedFile | None = File(None),
):
    """ create new reciter """

    if Reciter.objects.filter(reciter_identifier=data.reciter_identifier).exists():
        raise ItqanError(
            error_name="duplicate_reciter_identifier",
            message="Reciter with this identifier already exists.",
            status_code=400,
        )


    if Reciter.objects.filter(name=data.name).exists():
        raise ItqanError(
            error_name="duplicate_name",
            message="Reciter with this name already exists.",
            status_code=400,
        )

    reciter = Reciter.objects.create(**data.dict())

    if image:
        reciter.image_url.save(image.name, image, save=True)

    return reciter
