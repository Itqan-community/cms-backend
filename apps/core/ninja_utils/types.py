from typing import Annotated, TypedDict

from pydantic import PlainSerializer
from pydantic_core.core_schema import SerializationInfo

from apps.core.ninja_utils.request import Request


class SerializationInfoDict(TypedDict):
    request: Request
    response_status: int


def _build_url(url: str, info: SerializationInfo[SerializationInfoDict]) -> str:
    if not url:
        return url
    request = info.context["request"]
    return request.build_absolute_uri(url)


AbsoluteUrl = Annotated[str, PlainSerializer(_build_url, return_type=str)]

__all__ = [AbsoluteUrl]
