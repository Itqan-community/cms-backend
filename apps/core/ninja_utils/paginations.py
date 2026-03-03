import math
from typing import Any

from django.db.models import QuerySet
from ninja import Schema
from ninja.pagination import PageNumberPagination as NinjaPageNumberPagination
from pydantic import Field

MAX_PAGE_SIZE = 1000
DEFAULT_PAGE_SIZE = 20


class NinjaPagination(NinjaPageNumberPagination):
    items_attribute: str = "results"

    class Input(Schema):
        page: int = Field(1, ge=1)
        page_size: int = Field(DEFAULT_PAGE_SIZE, ge=1)

        def __init__(self, page_size: int = DEFAULT_PAGE_SIZE, **kwargs: Any) -> None:
            self.page_size = min(page_size, MAX_PAGE_SIZE)
            super().__init__(**kwargs)

    class Output(Schema):
        results: list[Any]
        total: int
        page: int
        page_size: int
        total_pages: int
        next_page: int | None
        prev_page: int | None

    def paginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        **params: Any,
    ) -> Any:
        total = self._items_count(queryset)
        page = pagination.page
        page_size = pagination.page_size
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        offset = (page - 1) * page_size
        return {
            "results": queryset[offset : offset + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "next_page": page + 1 if page < total_pages else None,
            "prev_page": page - 1 if page > 1 and page <= total_pages + 1 else None,
        }

    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        **params: Any,
    ) -> Any:
        total = await self._aitems_count(queryset)
        page = pagination.page
        page_size = pagination.page_size
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        offset = (page - 1) * page_size
        return {
            "results": queryset[offset : offset + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "next_page": page + 1 if page < total_pages else None,
            "prev_page": page - 1 if page > 1 and page <= total_pages + 1 else None,
        }
