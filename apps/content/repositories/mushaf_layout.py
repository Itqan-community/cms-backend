"""ORM access for MushafLayout writes."""

from __future__ import annotations

from apps.content.models import MushafLayout


class MushafLayoutRepository:
    def __init__(self) -> None:
        self.model = MushafLayout

    def get(self, layout_id: int) -> MushafLayout | None:
        return self.model.objects.filter(pk=layout_id).first()

    def create(self, **fields) -> MushafLayout:
        return self.model.objects.create(**fields)

    def update(self, layout: MushafLayout, **fields) -> MushafLayout:
        for name, value in fields.items():
            setattr(layout, name, value)
        layout.save(update_fields=[*fields.keys(), "updated_at"])
        return layout

    def delete(self, layout: MushafLayout) -> None:
        layout.delete()

    def is_in_use(self, layout: MushafLayout) -> bool:
        return layout.assets.exists()
