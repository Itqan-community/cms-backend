import dataclasses
from decimal import Decimal

from django.utils import translation
from ninja import FilterSchema
from ninja import Query
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag


@dataclasses.dataclass
class Course:
    id: int
    title: str
    description: str
    cover_photo: object


router = ItqanRouter(tags=[NinjaTag.COURSES])


class CourseListSchema(Schema):
    id: int
    title: str
    cover_photo: str | None = None
    progress: Decimal = Decimal("0.0")
    order: int = 0

    @staticmethod
    def resolve_cover_photo(course: Course) -> str | None:
        return course.cover_photo.url if course.cover_photo else None

    @staticmethod
    def resolve_order(course: Course) -> int:
        return course.temp_course_order or 0


class CourseFilters(FilterSchema):
    progress_gte: Decimal | None = Field(None, q="progress__gte")
    progress_lte: Decimal | None = Field(None, q="progress__lte")
    progress_gt: Decimal | None = Field(None, q="progress__gt")
    progress_lt: Decimal | None = Field(None, q="progress__lt")


@router.get("catalog/courses/", response=list[CourseListSchema])
@paginate
@ordering(ordering_fields=["order", "id", "title", "progress"])
@searching(search_fields=["title", "description"])
def list_courses(request, filters: CourseFilters = Query(...)):
    lang = translation.get_language_from_request(request, check_path=False) or "ar"

    courses = (
        Course.objects.filter(languages__contains=[lang]).visible_for(request.user).annotate_progress(request.user)
    )

    courses = filters.filter(courses)

    return courses.distinct()
