import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any, cast, overload

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import QuerySet
from django.utils.module_loading import import_string
from ninja import Query, Schema
from ninja.constants import NOT_SET
from ninja.signature import is_async
from ninja.utils import contribute_operation_args

__all__ = [
    "AsyncSearchOperation",
    "SearchOperation",
    "SearchingBase",
    "searching",
]


class SearchingBase(ABC):
    class Input(Schema): ...

    InputSource = Query(...)

    def __init__(
        self,
        *,
        pass_parameter: str | None = None,
        search_fields: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.pass_parameter = pass_parameter
        self.search_fields = search_fields or []

    @abstractmethod
    def searching_queryset(
        self, items: QuerySet | list, searching_input: Any
    ) -> QuerySet | list: ...


@overload
def searching() -> Callable[..., Any]:  # pragma: no cover
    ...


@overload
def searching(
    func_or_searching_class: Any = NOT_SET,
    **searching_params: Any,
) -> Callable[..., Any]:  # pragma: no cover
    ...


def searching(
    func_or_searching_class: Any = NOT_SET, **searching_params: Any
) -> Callable[..., Any]:
    isfunction = inspect.isfunction(func_or_searching_class)
    isnotset = func_or_searching_class == NOT_SET

    settings_class = settings.NINJA_SEARCHING_CLASS
    searching_class: type[SearchingBase] = (
        import_string(settings_class) if isinstance(settings_class, str) else settings_class
    )

    if isfunction:
        return _inject_searcher(func_or_searching_class, searching_class)

    if not isnotset:
        searching_class = func_or_searching_class

    def wrapper(func: Callable[..., Any]) -> Any:
        return _inject_searcher(func, searching_class, **searching_params)

    return wrapper


def _inject_searcher(
    func: Callable[..., Any],
    searching_class: type[SearchingBase],
    **searching_params: Any,
) -> Callable[..., Any]:
    searcher: SearchingBase = searching_class(**searching_params)
    searcher_kwargs_name = "searching"
    search_operation_class = AsyncSearchOperation if is_async(func) else SearchOperation
    searcher_operation = search_operation_class(
        searcher=searcher, view_func=func, searcher_kwargs_name=searcher_kwargs_name
    )

    return searcher_operation.as_view


class SearchOperation:
    def __init__(
        self,
        *,
        searcher: SearchingBase,
        view_func: Callable,
        searcher_kwargs_name: str = "searching",
    ) -> None:
        self.searcher = searcher
        self.searcher_kwargs_name = searcher_kwargs_name
        self.view_func = view_func

        searcher_view = self.get_view_function()
        self.as_view = wraps(view_func)(searcher_view)

        contribute_operation_args(
            self.as_view,
            self.searcher_kwargs_name,
            self.searcher.Input,
            self.searcher.InputSource,
        )
        searcher_view.searcher_operation = self  # type:ignore[attr-defined]

    @property
    def view_func_has_kwargs(self) -> bool:  # pragma: no cover
        return self.searcher.pass_parameter is not None

    def get_view_function(self) -> Callable:
        def as_view(*args: Any, **kw: Any) -> Any:
            func_kwargs = dict(**kw)
            searching_params = func_kwargs.pop(self.searcher_kwargs_name)
            if self.searcher.pass_parameter:
                func_kwargs[self.searcher.pass_parameter] = searching_params

            items = self.view_func(*args, **func_kwargs)
            return self.searcher.searching_queryset(items, searching_params)

        return as_view


class AsyncSearchOperation(SearchOperation):
    def get_view_function(self) -> Callable:
        async def as_view(*args: Any, **kw: Any) -> Any:
            func_kwargs = dict(**kw)
            searching_params = func_kwargs.pop(self.searcher_kwargs_name)
            if self.searcher.pass_parameter:
                func_kwargs[self.searcher.pass_parameter] = searching_params

            items = await self.view_func(*args, **func_kwargs)
            searching_queryset = cast("Callable", sync_to_async(self.searcher.searching_queryset))
            return await searching_queryset(items, searching_params)

        return as_view
