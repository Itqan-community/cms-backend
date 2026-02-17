from ninja import Schema

from apps.content.models import Resource
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RESOURCES])


class CategoryOut(Schema):
    value: str
    label: str


@router.get("categories/", response=list[CategoryOut])
def list_categories(request: Request):
    return [CategoryOut(value=choice.value, label=str(choice.label)) for choice in Resource.CategoryChoice]
