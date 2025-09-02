from django.apps import AppConfig


class SearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.search'
    
    def ready(self):
        # Import signal handlers when app is ready
        import apps.search.signals
