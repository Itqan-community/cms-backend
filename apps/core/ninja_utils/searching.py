from collections.abc import Callable
from functools import reduce
import operator
import re
from typing import Any

from django.db.models import Q, QuerySet
from django.db.models.constants import LOOKUP_SEP
from ninja import P, Query, Schema
from pydantic import Field

from apps.core.ninja_utils.searching_base import SearchingBase


def _istartswith(a: str, b: str) -> bool:
    return a.startswith(b)


def _isiexact(a: str, b: str) -> bool:
    return a.lower() == b.lower()


def _isiregex(a: str, b: str) -> bool:
    return bool(re.search(b, a, re.IGNORECASE))


def _isicontains(a: str, b: str) -> bool:
    return b.lower() in a.lower()


class Searching(SearchingBase):
    class Input(Schema):
        """just for reference will be replaced by create_input"""

        search: str | None = Field(None)

    lookup_prefixes = {
        "^": "istartswith",
        "=": "iexact",
        "@": "search",
        "$": "iregex",
    }

    lookup_prefixes_list = {
        "^": _istartswith,
        "=": _isiexact,
        "$": _isiregex,
    }

    def __init__(
        self,
        search_fields: list[str] | None = None,
        pass_parameter: str | None = None,
        query_param: str = "search",
    ) -> None:
        super().__init__(pass_parameter=pass_parameter)
        self.search_fields = search_fields or []
        self.query_param = query_param
        self.Input = self.create_input(search_fields)  # type:ignore

    def create_input(self, search_fields: list[str] | None) -> type[Input]:
        query_param = self.query_param
        if search_fields:

            class DynamicInput(Searching.Input):
                search: Query[
                    str | None,
                    P(example=", ".join(search_fields), alias=query_param),
                ] = None  # type:ignore[type-arg,valid-type]

            return DynamicInput
        return Searching.Input

    def searching_queryset(self, items: QuerySet | list, searching_input: Input) -> QuerySet | list:
        search_terms = self.get_search_terms(searching_input.search)

        if self.search_fields and search_terms:
            if isinstance(items, QuerySet):
                conditions_queryset = self.construct_conditions_for_queryset(search_terms)
                return items.filter(reduce(operator.and_, conditions_queryset))
            elif isinstance(items, list):
                conditions_list = self.construct_conditions_for_list(search_terms)
                return [item for item in items if self.filter_spec(item, conditions_list)]
        return items

    def get_search_terms(self, value: str | None) -> list[str]:
        if value:
            value = value.replace("\x00", "")  # strip null characters
            value = value.replace(",", " ")
            return value.split()
        return []

    def construct_search(self, field_name: str) -> str:
        lookup = self.lookup_prefixes.get(field_name[0])
        if lookup:
            field_name = field_name[1:]
        else:
            lookup = "icontains"
        return LOOKUP_SEP.join([field_name, lookup])

    def construct_conditions_for_queryset(self, search_terms: list[str]) -> list[Q]:
        orm_lookups = [self.construct_search(str(search_field)) for search_field in self.search_fields]

        conditions = []
        for search_term in search_terms:
            queries = [Q(**{orm_lookup: search_term}) for orm_lookup in orm_lookups]
            conditions.append(reduce(operator.or_, queries))
        return conditions

    def construct_conditions_for_list(self, search_terms: list[str]) -> dict[str, list[tuple[Callable, str]]]:
        lookups = self.construct_search_for_list()
        conditions: dict[str, list[tuple[Callable, str]]] = {field_name: [] for field_name in lookups}
        for search_term in search_terms:
            for field_name, lookup in lookups.items():
                conditions[field_name].append((lookup, search_term))
        return conditions

    def construct_search_for_list(self) -> dict[str, Callable]:
        def get_lookup(prefix: str) -> Callable:
            return self.lookup_prefixes_list.get(prefix, _isicontains)

        return {
            (field_name[1:] if (self.lookup_prefixes_list.get(field_name[0])) else field_name): get_lookup(
                field_name[0]
            )
            for field_name in self.search_fields
        }

    def filter_spec(self, item: Any, conditions: dict[str, list[tuple[Callable, str]]]) -> bool:
        item_getter = operator.itemgetter if isinstance(item, dict) else operator.attrgetter
        for field, lookup in conditions.items():
            if not any(lookup_func(item_getter(field)(item), lookup_value) for lookup_func, lookup_value in lookup):
                return False
        return True
