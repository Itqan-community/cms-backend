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
