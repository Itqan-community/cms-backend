from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    
    def ready(self):
        """Import admin configuration when app is ready"""
        # Import admin configuration to set up custom admin interface
        from . import admin
        
        # Run final admin cleanup after all apps are loaded
        # This ensures any models registered by other apps after our initial setup are handled
        admin.final_admin_cleanup()