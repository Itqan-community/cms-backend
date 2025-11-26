from __future__ import annotations

from collections.abc import Iterable

from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class DeleteFilesOnDeleteMixin:
    """
    Mixin to ensure any FileField/ImageField files are deleted from storage
    when the model instance is deleted.

    Attach to any model that has FileField/ImageField. Works with bulk deletes
    as we hook into post_delete and iterate the instance's file fields.
    """

    @classmethod
    def _iter_file_fields(cls) -> Iterable[models.Field]:
        for field in cls._meta.get_fields():  # type: ignore[attr-defined]
            if isinstance(field, (models.FileField | models.ImageField)):
                yield field


@receiver(post_delete)
def delete_associated_files_on_delete(sender, instance, **kwargs):
    """
    Global receiver: only acts for instances that subclass DeleteFilesOnDeleteMixin.
    Deletes all FileField/ImageField from storage without saving the model again.
    """
    if not isinstance(instance, DeleteFilesOnDeleteMixin):
        return
    try:
        for field in instance._iter_file_fields():  # type: ignore[attr-defined]
            try:
                f = getattr(instance, field.name, None)
                if f and getattr(f, "name", ""):
                    f.delete(save=False)
            except Exception:
                # Best-effort: ignore storage errors during cleanup
                pass
    except Exception:
        # Do not raise from signals
        pass
