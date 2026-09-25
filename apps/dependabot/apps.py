from django.apps import AppConfig


class DependabotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dependabot"

    def ready(self) -> None:
        import apps.dependabot.signals  # noqa: F401
