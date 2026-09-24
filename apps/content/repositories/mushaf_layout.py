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

        update_fields = list(fields.keys())
        if "name_ar" in fields or "name_en" in fields:
            # `name` is the original modeltranslation field: reading it always
            # dynamically resolves from name_<active-language> with fallback
            # (MODELTRANSLATION_FALLBACK_LANGUAGES), never from a raw value
            # assigned to it. That resolved value only reaches the database if
            # "name" is itself part of update_fields, so it must be added
            # explicitly whenever a localized name changes.
            update_fields.append("name")

        layout.save(update_fields=[*update_fields, "updated_at"])
        return layout

    def delete(self, layout: MushafLayout) -> None:
        layout.delete()

    def is_in_use(self, layout: MushafLayout) -> bool:
        return layout.assets.exists()
