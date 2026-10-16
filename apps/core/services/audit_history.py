from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db import IntegrityError, models, transaction
from django.utils.translation import gettext_lazy as _
from simple_history.exceptions import NotHistoricalModelError

from apps.core.ninja_utils.errors import ItqanError
from apps.core.repositories.audit_history import AuditHistoryRepository

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)


class AuditHistoryService:
    """Service providing audit trail inspection and snapshot restoration capabilities."""

    def __init__(self, repo: AuditHistoryRepository | None = None) -> None:
        self.repo = repo or AuditHistoryRepository()

    def resolve_model(self, model_or_str: type[models.Model] | str | models.Model) -> type[models.Model]:
        """Resolves a model string or class into a verified history-tracked model."""
        if isinstance(model_or_str, str):
            parts = model_or_str.split(".", 1)
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid model identifier '{model_or_str}'. Expected format: '<app_label>.<ModelName>'."
                )
            app_label, model_name = parts
            return self.repo.get_tracked_model(app_label, model_name)

        if isinstance(model_or_str, models.Model):
            model_cls = model_or_str.__class__
        elif isinstance(model_or_str, type) and issubclass(model_or_str, models.Model):
            model_cls = model_or_str
        else:
            raise TypeError(f"Expected a Django Model class or identifier, got {type(model_or_str)}.")

        if not hasattr(model_cls._meta, "simple_history_manager_attribute"):
            raise NotHistoricalModelError(f"Model '{model_cls._meta.label}' does not have history tracking enabled.")
        return model_cls

    def get_object_history(
        self, model_or_str: type[models.Model] | str | models.Model, object_id: Any
    ) -> list[dict[str, Any]]:
        """Returns ordered audit trail entries for a given object."""
        model = self.resolve_model(model_or_str)
        records = self.repo.get_history_records(model, object_id)

        history_list = []
        for record in records:
            history_list.append(
                {
                    "history_id": record.history_id,
                    "history_date": record.history_date,
                    "history_type": record.history_type,
                    "history_type_display": {
                        "+": _("Created"),
                        "~": _("Updated"),
                        "-": _("Deleted"),
                    }.get(record.history_type, record.history_type),
                    "history_user_id": record.history_user_id,
                    "history_change_reason": record.history_change_reason or "",
                }
            )
        return history_list

    def restore_object_version(
        self,
        model_or_str: type[models.Model] | str | models.Model,
        object_id: Any,
        version_id: Any | None = None,
        as_of: datetime | None = None,
        user: Any | None = None,
        change_reason: str = "",
    ) -> tuple[models.Model, Any]:
        """Restores a tracked model instance to a chosen historical version or snapshot.

        Supports:
        - Reverting an existing modified object back to prior values (Edit -> Revert).
        - Resurrecting a deleted row from historical tables back into operational DB (Delete -> Restore).
        - Automatically writes a new auditable historical entry with user attribution.

        Args:
            model_or_str: Model class, 'app.Model' string, or model instance.
            object_id: Primary key of the object to restore.
            version_id: Specific historical record ID (history_id) to restore.
            as_of: Datetime snapshot to restore to (if version_id is not provided).
            user: User performing the restoration (for audit attribution).
            change_reason: Custom reason for audit log (defaults to descriptive message).

        Returns:
            Tuple of (restored_operational_instance, new_audit_record).
        """
        model = self.resolve_model(model_or_str)
        exists = self.repo.object_exists(model, object_id)

        if version_id is not None:
            target_record = self.repo.get_historical_record_by_id(model, object_id, version_id)
            if not target_record:
                raise ItqanError(
                    error_name="historical_record_not_found",
                    message=_("Historical version with ID '{version_id}' not found for this object.").format(
                        version_id=version_id
                    ),
                    status_code=404,
                )
        elif as_of is not None:
            target_record = self.repo.get_historical_record_as_of(model, object_id, as_of)
            if not target_record:
                raise ItqanError(
                    error_name="historical_snapshot_not_found",
                    message=_("No historical snapshot found on or before '{date}'.").format(date=as_of),
                    status_code=404,
                )
        else:
            if not exists:
                # If row was deleted and no version specified, restore from latest historical snapshot
                target_record = self.repo.get_latest_valid_record(model, object_id)
                if not target_record:
                    raise ItqanError(
                        error_name="no_history_for_object",
                        message=_("No historical records found for object ID '{object_id}'.").format(
                            object_id=object_id
                        ),
                        status_code=404,
                    )
            else:
                raise ItqanError(
                    error_name="version_or_as_of_required",
                    message=_("You must specify either 'version_id' or 'as_of' to revert an existing object."),
                    status_code=400,
                )

        restored_instance = target_record.instance
        is_resurrection = not exists

        if not change_reason:
            if is_resurrection:
                change_reason = f"Restored deleted object from historical version {target_record.history_id}"
            else:
                change_reason = f"Reverted to historical version {target_record.history_id}"

        try:
            with transaction.atomic():
                saved_instance = self.repo.save_restored_instance(
                    instance=restored_instance,
                    is_resurrection=is_resurrection,
                    user=user,
                    change_reason=change_reason,
                )
        except IntegrityError as exc:
            logger.error(
                f"Failed to restore object {model._meta.label} ID {object_id}: {exc}",
                exc_info=True,
            )
            raise ItqanError(
                error_name="restoration_integrity_error",
                message=_(
                    "Cannot restore object due to a database integrity constraint (such as a missing foreign key)."
                ),
                status_code=400,
                extra={"detail": str(exc)},
            ) from exc

        # Retrieve the newly generated historical record in audit DB
        new_audit_record = self.repo.get_history_records(model, object_id).first()

        action_name = "resurrected" if is_resurrection else "reverted"
        logger.info(
            f"Object {model._meta.label} (ID: {object_id}) {action_name} to history_id {target_record.history_id} "
            f"[new_history_id={getattr(new_audit_record, 'history_id', None)}, user={user}]"
        )

        return saved_instance, new_audit_record
