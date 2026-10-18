from django.apps import AppConfig


class UsageTrackingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.usage_tracking"

    def ready(self) -> None:
        from django.core import checks

        from apps.usage_tracking.checks import check_usage_identity_key

        checks.register(check_usage_identity_key)
