AUDIT_APP_LABEL = "simple_history"


class AuditRouter:
    """
    Routes django-simple-history models to the "audit" database,
    other models are routed to the "default" database.

    NOTE: Every `HistoricalRecords()` call MUST be instantiated with:
    - `app="simple_history"` (matching AUDIT_APP_LABEL above)
    - `use_base_model_db=False`
    - `history_user_id_field=models.BigIntegerField(null=True)` (plain scalar id, no cross-DB FK)
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label == AUDIT_APP_LABEL:
            return "audit"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == AUDIT_APP_LABEL:
            return "audit"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._meta.app_label == AUDIT_APP_LABEL and obj2._meta.app_label == AUDIT_APP_LABEL:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == AUDIT_APP_LABEL:
            return db == "audit"
        return db == "default"
