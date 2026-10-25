from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.db import models
from simple_history.exceptions import NotHistoricalModelError

if TYPE_CHECKING:
    from datetime import datetime

    from django.db.models import QuerySet


class AuditHistoryRepository:
    """Repository handling database operations for audit history and model snapshot restoration."""

    def get_tracked_model(self, app_label: str, model_name: str) -> type[models.Model]:
        """Resolves model class and verifies that simple-history is configured on it."""
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError as e:
            raise LookupError(f"Model '{app_label}.{model_name}' not found.") from e

        if not hasattr(model._meta, "simple_history_manager_attribute"):
            raise NotHistoricalModelError(f"Model '{app_label}.{model_name}' does not have history tracking enabled.")
        return model

    def get_history_manager(self, model: type[models.Model]):
        """Returns the simple-history manager for the model."""
        if not hasattr(model._meta, "simple_history_manager_attribute"):
            raise NotHistoricalModelError(f"Model '{model._meta.label}' does not have history tracking enabled.")
        return getattr(model, model._meta.simple_history_manager_attribute)

    def get_history_records(self, model: type[models.Model], object_id: Any) -> QuerySet:
        """Returns queryset of historical records for the object, newest first."""
        history_mgr = self.get_history_manager(model)
        pk_name = model._meta.pk.name
        return history_mgr.filter(**{pk_name: object_id}).order_by("-history_date", "-history_id")

    def get_historical_record_by_id(self, model: type[models.Model], object_id: Any, history_id: Any) -> Any | None:
        """Fetches a specific historical record by history_id and object_id."""
        history_mgr = self.get_history_manager(model)
        pk_name = model._meta.pk.name
        return history_mgr.filter(**{pk_name: object_id, "history_id": history_id}).first()

    def get_historical_record_as_of(self, model: type[models.Model], object_id: Any, date: datetime) -> Any | None:
        """Fetches the latest historical record on or before a given datetime."""
        history_mgr = self.get_history_manager(model)
        pk_name = model._meta.pk.name
        return (
            history_mgr.filter(**{pk_name: object_id, "history_date__lte": date})
            .order_by("-history_date", "-history_id")
            .first()
        )

    def get_latest_valid_record(self, model: type[models.Model], object_id: Any) -> Any | None:
        """Fetches the latest historical record for the object (e.g. state at or before deletion)."""
        history_mgr = self.get_history_manager(model)
        pk_name = model._meta.pk.name
        return history_mgr.filter(**{pk_name: object_id}).order_by("-history_date", "-history_id").first()

    def object_exists(self, model: type[models.Model], object_id: Any) -> bool:
        """Checks if the object currently exists in the operational table (default DB)."""
        return model.objects.filter(pk=object_id).exists()

    def get_operational_object(self, model: type[models.Model], object_id: Any) -> models.Model | None:
        """Fetches the current object from the operational table (default DB)."""
        return model.objects.filter(pk=object_id).first()

    def save_restored_instance(
        self,
        instance: models.Model,
        is_resurrection: bool,
        user: Any | None = None,
        change_reason: str = "",
    ) -> models.Model:
        """Persists the restored instance into the operational database.

        If is_resurrection is True, forces an INSERT so the deleted row is recreated
        with its original primary key.
        If is_resurrection is False, updates the existing row in default DB.
        Attaches _history_user and _change_reason so simple-history records the action in audit DB.
        """
        instance._history_user = user
        instance._change_reason = change_reason
        instance._state.db = "default"

        if is_resurrection:
            instance._state.adding = True
            instance.save(force_insert=True)
        else:
            instance._state.adding = False
            instance.save(force_update=True)

        return instance
