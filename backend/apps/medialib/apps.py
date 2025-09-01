"""
Media Library App Configuration
"""
from django.apps import AppConfig


class MedialibConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.medialib'
    verbose_name = 'Media Library'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import apps.medialib.signals  # noqa
        except ImportError:
            pass