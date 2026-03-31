import math
from typing import Any
from urllib.parse import urlencode

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
        page_size: int = Field(DEFAULT_PAGE_SIZE, ge=1)

        @field_validator("page_size")
        @classmethod
        def clamp_page_size(cls, v: int) -> int:
            return min(v, MAX_PAGE_SIZE)

    class Output(Schema):
        results: list[Any]
        total: int
        page: int
        page_size: int
        total_pages: int
        next_page: str | None
        prev_page: str | None

    @staticmethod
    def _build_page_url(request: HttpRequest | None, page: int, page_size: int) -> str | None:
        if request is None:
            return None
        query = request.GET.copy()
        query["page"] = str(page)
        query["page_size"] = str(page_size)
        return f"{request.path}?{urlencode(query, doseq=True)}"

    def _build_response(
        self,
        queryset: QuerySet,
        pagination: "NinjaPagination.Input",
        count: int,
        request: HttpRequest | None = None,
    ) -> dict[str, Any]:
        page = pagination.page
        page_size = pagination.page_size
        total_pages = math.ceil(count / page_size) if page_size else 0
        offset = (page - 1) * page_size

        return {
            "results": queryset[offset : offset + page_size],
            "total": count,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "next_page": self._build_page_url(request, page + 1, page_size) if page < total_pages else None,
            "prev_page": self._build_page_url(request, page - 1, page_size) if page > 1 else None,
        }

    def paginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        **params: Any,
    ) -> Any:
        count = self._items_count(queryset)
        request = params.get("request")
        return self._build_response(queryset, pagination, count, request)

    async def apaginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        **params: Any,
    ) -> Any:
        count = await self._aitems_count(queryset)
        request = params.get("request")
        return self._build_response(queryset, pagination, count, request)
