from __future__ import annotations

from typing import Any

from apps.content.models import Reciter
from apps.core.slugs import slugify_name


class ReciterRepository:
    def __init__(self) -> None:
        self.model = Reciter

    def _derive_slug(self, name_en: str | None, name_ar: str | None) -> str:
        """
        Derive a deterministic slug, preferring name_en and falling back to name_ar.
        """
        return slugify_name(name_en, name_ar)

    def create_reciter(self, **kwargs: Any) -> Reciter:
        """
        Create a new reciter.
        """
        if "slug" not in kwargs:
            slug = self._derive_slug(kwargs.get("name_en", ""), kwargs.get("name_ar", ""))
            if slug:
                kwargs["slug"] = slug
        return self.model.objects.create(**kwargs)

    def update_reciter(self, reciter: Reciter, fields: dict[str, Any]) -> Reciter:
        """
        Update a reciter using provided fields.
        """
        changed_fields = []
        for key, value in fields.items():
            if hasattr(reciter, key):
                setattr(reciter, key, value)
                changed_fields.append(key)

        # Determine base name for slugification
        if "name_ar" in changed_fields or "name_en" in changed_fields:
            new_name_ar = fields.get("name_ar", getattr(reciter, "name_ar", "")) or ""
            new_name_en = fields.get("name_en", getattr(reciter, "name_en", "")) or ""
            slug = self._derive_slug(new_name_en, new_name_ar)
            if slug:
                reciter.slug = slug
                changed_fields.append("slug")

        if changed_fields:
            changed_fields.append("updated_at")
            # De-duplicate fields
            update_fields_set = set(changed_fields)
            if "image_url" in update_fields_set:
                # image_url is an ImageField, simple update_fields might need special care
                pass
            reciter.save(update_fields=list(update_fields_set) if "image_url" not in update_fields_set else None)

        return reciter

    def delete_reciter(self, reciter: Reciter) -> None:
        """
        Delete a reciter.
        """
        reciter.delete()
