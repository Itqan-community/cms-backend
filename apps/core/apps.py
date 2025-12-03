from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self) -> None:
        # Import signal handlers for storage cleanup on model delete
        from .mixins import storage  # noqa: F401

        return super().ready()
