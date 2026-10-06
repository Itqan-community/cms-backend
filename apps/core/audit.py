"""Audit historical records descriptor configured for Itqan CMS."""

from django.db import models
from simple_history.models import HistoricalRecords


class AuditHistoricalRecords(HistoricalRecords):
    """HistoricalRecords subclass configured for the dual-database audit architecture:

    - Automatically defaults app='simple_history' (for AuditRouter).
    - Defaults use_base_model_db=False so records route to 'audit' database.
    - Defaults history_user_id_field to scalar BigIntegerField(null=True) to eliminate
      cross-database ForeignKeys.
    - Handles django-modeltranslation by downgrading TranslationField instances to
      their plain base field types and stripping unique constraints (which are invalid
      in append-only historical tables).
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("app", "simple_history")
        kwargs.setdefault("use_base_model_db", False)
        kwargs.setdefault(
            "history_user_id_field",
            models.BigIntegerField(null=True),
        )
        super().__init__(**kwargs)

    def copy_fields(self, model):
        fields = super().copy_fields(model)
        for field in fields.values():
            if hasattr(field, "translated_field"):
                # Downgrade modeltranslation proxy field to the plain underlying field
                field.__class__ = field.translated_field.__class__
                field.unique = False
                field._unique = False
        return fields


def update_with_history(
    queryset,
    batch_size: int | None = None,
    default_user=None,
    default_change_reason: str = "",
    **fields,
) -> int:
    """Updates a queryset of model instances while preserving simple_history.

    Django's native `queryset.update(...)` bypasses post_save signals, meaning no
    historical records are generated. This helper fetches matching instances, updates
    the target attributes in memory, and persists both the model changes and historical
    records via `simple_history.utils.bulk_update_with_history`.

    Args:
        queryset: QuerySet of instances to update.
        batch_size: Optional batch size for bulk operations.
        default_user: Optional user to attribute the change to (falls back to request user).
        default_change_reason: Optional reason string for the historical change.
        **fields: Field-value pairs to update on each instance.

    Returns:
        The number of updated rows.
    """
    from django.db.models.expressions import Combinable
    from simple_history.utils import bulk_update_with_history

    for field, value in fields.items():
        if isinstance(value, Combinable):
            raise ValueError(
                f"Expression values (like F()) are not supported in update_with_history "
                f"(field '{field}'). Resolve expressions to concrete values before updating."
            )

    instances = list(queryset)
    if not instances:
        return 0

    for instance in instances:
        for field, value in fields.items():
            setattr(instance, field, value)

    rows_updated = bulk_update_with_history(
        instances,
        queryset.model,
        list(fields.keys()),
        batch_size=batch_size,
        default_user=default_user,
        default_change_reason=default_change_reason,
    )
    return rows_updated if rows_updated is not None else len(instances)
