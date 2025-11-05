from typing import Generic, TypeVar

from ninja import Schema

ERROR_NAME = TypeVar("ERROR_NAME")
EXTRA_TYPE = TypeVar("EXTRA_TYPE")


class NinjaErrorResponse(Generic[ERROR_NAME, EXTRA_TYPE], Schema):
    error_name: ERROR_NAME
    message: str
    extra: EXTRA_TYPE | None = None
