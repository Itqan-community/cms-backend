from typing import Annotated

from pydantic import PlainSerializer
from pydantic_core.core_schema import SerializationInfo


def _build_url(url: str, info: SerializationInfo):
    if not url:
        return url
    request = info.context["request"]
    return request.build_absolute_uri(url)


AbsoluteUrl = Annotated[str, PlainSerializer(_build_url, return_type=str)]
