from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import Count, Q
from django.utils.text import slugify

from apps.content.models import Reciter, Resource

if TYPE_CHECKING:
    from django.db.models import QuerySet


class ReciterRepository:
    def __init__(self) -> None:
        self.model = Reciter

    def list_reciters_qs(self) -> QuerySet[Reciter]:
        """
        Returns a queryset of Reciter models with their recitations_count annotated.
        """
        recitation_filter = Q(
            assets__category=Resource.CategoryChoice.RECITATION,
            assets__resource__category=Resource.CategoryChoice.RECITATION,
            assets__resource__status=Resource.StatusChoice.READY,
        )

        qs = self.model.objects.annotate(
            recitations_count=Count(
                "assets",
                filter=recitation_filter,
                distinct=True,
            )
        )
        return qs

    def get_reciter(self, reciter_slug: str) -> Reciter | None:
        """
        Get a single reciter by slug.
        """
        try:
            return self.list_reciters_qs().get(slug=reciter_slug)
        except Reciter.DoesNotExist:
            return None

    def _derive_slug(self, name_en: str | None, name_ar: str | None) -> str:
        """
        Derive a deterministic slug preferring name_ar if available.
        """
        name_to_slugify = name_ar or name_en
        if name_to_slugify:
            return slugify(name_to_slugify[:50], allow_unicode=True)
        return ""

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
