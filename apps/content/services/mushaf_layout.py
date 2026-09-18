"""Business rules for mushaf layouts (pagination referenced by page-based assets)."""

from __future__ import annotations

from django.utils.translation import gettext as _

from apps.content.models import MushafLayout
from apps.content.repositories.mushaf_layout import MushafLayoutRepository
from apps.core.ninja_utils.errors import ItqanError


class MushafLayoutService:
    def __init__(self, repo: MushafLayoutRepository | None = None) -> None:
        self.repo = repo or MushafLayoutRepository()

    def get_or_404(self, layout_id: int) -> MushafLayout:
        layout = self.repo.get(layout_id)
        if layout is None:
            raise ItqanError(
                error_name="mushaf_layout_not_found",
                message=_("Mushaf layout with id {id} not found.").format(id=layout_id),
                status_code=404,
            )
        return layout

    def create(self, *, name_ar: str | None, name_en: str | None, page_count: int) -> MushafLayout:
        return self.repo.create(name_ar=name_ar, name_en=name_en, page_count=page_count)

    def update(self, layout_id: int, **fields) -> MushafLayout:
        layout = self.get_or_404(layout_id)
        return self.repo.update(layout, **fields)

    def delete(self, layout_id: int) -> None:
        """Refuse to delete a layout any asset still points at.

        The FK is PROTECT, so the ORM would raise anyway — this turns that into
        a documented 400 instead of a 500.
        """
        layout = self.get_or_404(layout_id)
        if self.repo.is_in_use(layout):
            raise ItqanError(
                error_name="mushaf_layout_in_use",
                message=_("This layout is used by one or more assets and cannot be deleted."),
                status_code=400,
            )
        self.repo.delete(layout)
