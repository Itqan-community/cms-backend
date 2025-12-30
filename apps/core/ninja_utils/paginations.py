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

    def paginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        **params: Any,
    ) -> Any:
        offset = (pagination.page - 1) * pagination.page_size
        return {
            "results": queryset[offset : offset + pagination.page_size],
            "count": self._items_count(queryset),
        }

    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        **params: Any,
    ) -> Any:
        offset = (pagination.page - 1) * pagination.page_size
        return {
            "results": queryset[offset : offset + pagination.page_size],
            "count": await self._aitems_count(queryset),
        }
