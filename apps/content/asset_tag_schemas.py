"""What the APIs that describe text assets share: the tag shape and the category filter."""

from typing import Annotated

from django.utils.translation import gettext_lazy as _
from ninja import Schema
from pydantic import BeforeValidator

from apps.content.models import CategoryChoice
from apps.core.ninja_utils.errors import ItqanError

_RENAMED_CATEGORIES = frozenset({"tafsir", "translation"})


class AssetTagOut(Schema):
    """One tag on a text asset. ``name`` follows the request's language."""

    slug: str
    name: str


def _reject_renamed_category(value: object) -> object:
    """Tell clients that still send a pre-merge category what to send instead."""
    if value in _RENAMED_CATEGORIES:
        raise ItqanError(
            error_name="category_renamed",
            message=_("The {value} category is now the {tag} tag: use category=text&tag={tag}.").format(
                value=value, tag=value
            ),
            status_code=400,
        )
    return value


CategoryFilter = Annotated[CategoryChoice, BeforeValidator(_reject_renamed_category)]
