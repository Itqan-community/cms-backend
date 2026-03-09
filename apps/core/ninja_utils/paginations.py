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
        count: int
        total: int
        page: int
        page_size: int = Field(alias="pageSize")
        total_pages: int = Field(alias="totalPages")
        next_page: int | None = Field(None, alias="nextPage")
        prev_page: int | None = Field(None, alias="prevPage")

    def _build_pagination_response(
        self,
        queryset: QuerySet,
        pagination: Input,
        total: int,
    ) -> dict[str, Any]:
        offset = (pagination.page - 1) * pagination.page_size
        total_pages = math.ceil(total / pagination.page_size) if pagination.page_size > 0 else 0
        return {
            "results": queryset[offset : offset + pagination.page_size],
            "count": total,
            "total": total,
            "page": pagination.page,
            "pageSize": pagination.page_size,
            "totalPages": total_pages,
            "nextPage": pagination.page + 1 if pagination.page < total_pages else None,
            "prevPage": pagination.page - 1 if pagination.page > 1 else None,
        }

    def paginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        **params: Any,
    ) -> Any:
        total = self._items_count(queryset)
        return self._build_pagination_response(queryset, pagination, total)

    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        **params: Any,
    ) -> Any:
        total = await self._aitems_count(queryset)
        return self._build_pagination_response(queryset, pagination, total)
