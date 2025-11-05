from _operator import attrgetter, itemgetter
from django.db.models import QuerySet
from ninja import P, Query, Schema
from pydantic import BaseModel, Field

from apps.core.ninja_utils.ordering_base import OrderingBase

"""
ordering class, influences heavily by django-ninja-extra
"""


class Ordering(OrderingBase):
    class Input(Schema):
        ordering: str | None = Field(None)

    def __init__(
        self,
        ordering_fields: list[str] | None = None,
        pass_parameter: str | None = None,
        query_param: str = "ordering",
    ) -> None:
        super().__init__(pass_parameter=pass_parameter)
        self.ordering_fields = ordering_fields or []
        self.query_param = query_param
        self.Input = self.create_input(ordering_fields)  # type:ignore

    def create_input(self, ordering_fields: list[str] | None) -> type[Input]:
        query_param = self.query_param
        if ordering_fields:

            class DynamicInput(Ordering.Input):
                ordering: Query[
                    str | None, P(example=", ".join(ordering_fields), alias=query_param)
                ] = None  # type:ignore

            return DynamicInput
        return Ordering.Input

    def ordering_queryset(self, items: QuerySet | list, ordering_input: Input) -> QuerySet | list:
        ordering_ = self.get_ordering(items, ordering_input.ordering)
        if ordering_:
            if isinstance(items, QuerySet):
                return items.order_by(*ordering_)
            elif isinstance(items, list) and items:

                def multisort(xs: list, specs: list[tuple[str, bool]]) -> list:
                    sorter = itemgetter if isinstance(xs[0], dict) else attrgetter
                    for key, reverse in reversed(specs):
                        xs.sort(key=sorter(key), reverse=reverse)
                    return xs

                return multisort(
                    items,
                    [(o[int(o.startswith("-")) :], o.startswith("-")) for o in ordering_],
                )
        return items

    def get_ordering(self, items: QuerySet | list, value: str | None) -> list[str]:
        if value:
            fields = [param.strip() for param in value.split(",")]
            return self.remove_invalid_fields(items, fields)
        return []

    def remove_invalid_fields(self, items: QuerySet | list, fields: list[str]) -> list[str]:
        valid_fields = list(self.get_valid_fields(items))

        def term_valid(term: str) -> bool:
            if term.startswith("-"):
                term = term[1:]
            return term in valid_fields

        return [term for term in fields if term_valid(term)]

    def get_valid_fields(self, items: QuerySet | list) -> list[str]:
        valid_fields: list[str] = []
        if self.ordering_fields == "__all__":
            if isinstance(items, QuerySet):
                valid_fields = self.get_all_valid_fields_from_queryset(items)
            elif isinstance(items, list):
                valid_fields = self.get_all_valid_fields_from_list(items)
        else:
            valid_fields = list(self.ordering_fields)
        return valid_fields

    def get_all_valid_fields_from_queryset(self, items: QuerySet) -> list[str]:
        return [str(field.name) for field in items.model._meta.fields] + [
            str(key) for key in items.query.annotations
        ]

    def get_all_valid_fields_from_list(self, items: list) -> list[str]:
        if not items:
            return []
        item = items[0]
        if isinstance(item, BaseModel):
            return list(item.model_fields.keys())
        if isinstance(item, dict):
            return list(item.keys())
        if hasattr(item, "_meta") and hasattr(item._meta, "fields"):
            return [str(field.name) for field in item._meta.fields]
        return []
