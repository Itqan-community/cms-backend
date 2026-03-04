from django.apps import AppConfig


class PublishersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.publishers"

    def ready(self):
        import apps.publishers.signals