"""
Database router directing django-simple-history historical models to the
``audit`` database.

Historical models inherit the tracked model's ``app_label`` (e.g.
``HistoricalUser`` has ``app_label = "users"``), so the router inspects the
model class itself: every historical model inherits from
``simple_history.models.HistoricalChanges``.
"""

from simple_history.models import HistoricalChanges


def _is_history_model(model):
    """Return True if *model* is a django-simple-history historical model."""
    return model is not None and issubclass(model, HistoricalChanges)


class AuditRouter:
    """Route simple_history historical models to the 'audit' database."""

    def db_for_read(self, model, **hints):
        if _is_history_model(model):
            return "audit"
        return None

    def db_for_write(self, model, **hints):
        if _is_history_model(model):
            return "audit"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        model = hints.get("model")

        # Primary: model class available (standard migration operations).
        if model is not None:
            if _is_history_model(model):
                return db == "audit"
            if db == "audit":
                return False
            return None

        # Fallback: model class absent, model_name only.
        # Convention: application models must never use the "historical" prefix.
        if model_name is not None:
            if model_name.startswith("historical"):
                return db == "audit"
            if db == "audit":
                return False
            return None

        # No model info — protect audit DB, defer for others.
        if db == "audit":
            return False
        return None
