import math
from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest
from ninja import Schema
from ninja.pagination import PageNumberPagination as NinjaPageNumberPagination
from pydantic import Field, field_validator

MAX_PAGE_SIZE = 1000
DEFAULT_PAGE_SIZE = 20


class NinjaPagination(NinjaPageNumberPagination):
    items_attribute: str = "results"

    class Input(Schema):
        page: int = Field(1, ge=1)
        page_size: int = Field(DEFAULT_PAGE_SIZE, ge=1, alias="pageSize")

        model_config = {"populate_by_name": True}

        @field_validator("page_size")
        @classmethod
        def clamp_page_size(cls, value: int) -> int:
            return min(value, MAX_PAGE_SIZE)

    class Output(Schema):
        results: list[Any]
        count: int
        total: int
        page: int
        page_size: int = Field(alias="pageSize")
        total_pages: int = Field(alias="totalPages")
        next_page: str | None = Field(None, alias="nextPage")
        prev_page: str | None = Field(None, alias="prevPage")

    @staticmethod
    def _build_page_url(request: HttpRequest | None, page: int, page_size: int) -> str | None:
        if request is None:
            return None
        query = request.GET.copy()
        query["page"] = str(page)
        query["pageSize"] = str(page_size)
        if "page_size" in query:
            del query["page_size"]
        return f"{request.path}?{query.urlencode()}"

    def _build_pagination_response(
        self,
        queryset: QuerySet,
        pagination: Input,
        total: int,
        request: HttpRequest | None = None,
    ) -> dict[str, Any]:
        offset = (pagination.page - 1) * pagination.page_size
        total_pages = math.ceil(total / pagination.page_size) if pagination.page_size > 0 else 0
        next_page = (
            self._build_page_url(request, pagination.page + 1, pagination.page_size)
            if pagination.page < total_pages
            else None
        )
        prev_page = (
            self._build_page_url(request, pagination.page - 1, pagination.page_size)
            if pagination.page > 1
            else None
        )
        return {
            "results": queryset[offset : offset + pagination.page_size],
            "count": total,
            "total": total,
            "page": pagination.page,
            "pageSize": pagination.page_size,
            "totalPages": total_pages,
            "nextPage": next_page,
            "prevPage": prev_page,
        }

    def paginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        **params: Any,
    ) -> Any:
        total = self._items_count(queryset)
        request = params.get("request")
        return self._build_pagination_response(queryset, pagination, total, request)

    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        **params: Any,
    ) -> Any:
        total = await self._aitems_count(queryset)
        request = params.get("request")
        return self._build_pagination_response(queryset, pagination, total, request)
