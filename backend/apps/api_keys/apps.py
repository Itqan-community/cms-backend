"""
API Keys app configuration
"""
from django.apps import AppConfig


class ApiKeysConfig(AppConfig):
    """
    Configuration for API Keys app
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.api_keys'
    verbose_name = 'API Key Management'

    def ready(self):
        """
        Import signals when app is ready
        """
        try:
            from . import signals
        except ImportError:
            pass
