import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any, cast, overload

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.module_loading import import_string
from ninja import Query, Schema
from ninja.constants import NOT_SET
from ninja.signature import is_async
from ninja.utils import contribute_operation_args

__all__ = [
    "AsyncOrderingOperation",
    "OrderingBase",
    "OrderingOperation",
    "ordering",
]


class OrderingBase(ABC):
    class Input(Schema): ...

    InputSource = Query(...)

    def __init__(self, *, pass_parameter: str | None = None, **kwargs: Any) -> None:
        self.pass_parameter = pass_parameter

    @abstractmethod
    def ordering_queryset(self, items: QuerySet | list, ordering_input: Any) -> QuerySet | list: ...


@overload
def ordering() -> Callable[..., Any]:  # pragma: no cover
    ...


@overload
def ordering(
    func_or_ordering_class: Any = NOT_SET, **paginator_params: Any
) -> Callable[..., Any]:  # pragma: no cover
    ...


def ordering(func_or_ordering_class: Any = NOT_SET, **ordering_params: Any) -> Callable[..., Any]:
    isfunction = inspect.isfunction(func_or_ordering_class)
    isnotset = func_or_ordering_class == NOT_SET
    settings_class = settings.NINJA_ORDERING_CLASS
    ordering_class: type[OrderingBase] = (
        import_string(settings_class) if isinstance(settings_class, str) else settings_class
    )

    if isfunction:
        return _inject_sorter(func_or_ordering_class, ordering_class)

    if not isnotset:
        ordering_class = func_or_ordering_class

    def wrapper(func: Callable[..., Any]) -> Any:
        return _inject_sorter(func, ordering_class, **ordering_params)

    return wrapper


def _inject_sorter(
    func: Callable[..., Any],
    ordering_class: type[OrderingBase],
    **ordering_params: Any,
) -> Callable[..., Any]:
    sorter: OrderingBase = ordering_class(**ordering_params)
    sorter_kwargs_name = "ordering"
    sorter_operation_class = OrderingOperation
    if is_async(func):
        sorter_operation_class = AsyncOrderingOperation
    sorter_operation = sorter_operation_class(
        sorter=sorter, view_func=func, sorter_kwargs_name=sorter_kwargs_name
    )

    return sorter_operation.as_view


class OrderingOperation:
    def __init__(
        self,
        *,
        sorter: OrderingBase,
        view_func: Callable,
        sorter_kwargs_name: str = "ordering",
    ) -> None:
        self.sorter = sorter
        self.sorter_kwargs_name = sorter_kwargs_name
        self.view_func = view_func

        sorter_view = self.get_view_function()
        self.as_view = wraps(view_func)(sorter_view)
        contribute_operation_args(
            self.as_view,
            self.sorter_kwargs_name,
            self.sorter.Input,
            self.sorter.InputSource,
        )

        sorter_view.sorter_operation = self  # type:ignore[attr-defined]

    @property
    def view_func_has_kwargs(self) -> bool:  # pragma: no cover
        return self.sorter.pass_parameter is not None

    def get_view_function(self) -> Callable:
        def as_view(request: HttpRequest, *args: Any, **kw: Any) -> Any:
            func_kwargs = dict(**kw)
            ordering_params = func_kwargs.pop(self.sorter_kwargs_name)
            if self.sorter.pass_parameter:
                func_kwargs[self.sorter.pass_parameter] = ordering_params

            items = self.view_func(request, *args, **func_kwargs)
            return self.sorter.ordering_queryset(items, ordering_params)

        return as_view


class AsyncOrderingOperation(OrderingOperation):
    def get_view_function(self) -> Callable:
        async def as_view(request: HttpRequest, *args: Any, **kw: Any) -> Any:
            func_kwargs = dict(**kw)
            ordering_params = func_kwargs.pop(self.sorter_kwargs_name)
            if self.sorter.pass_parameter:
                func_kwargs[self.sorter.pass_parameter] = ordering_params

            items = await self.view_func(request, *args, **func_kwargs)
            ordering_queryset = cast("Callable", sync_to_async(self.sorter.ordering_queryset))
            return await ordering_queryset(items, ordering_params)

        return as_view
