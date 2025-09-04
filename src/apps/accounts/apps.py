"""
Django app configuration for Accounts app
"""
from django.apps import AppConfig
from django.contrib import admin


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        """
        Import signal handlers and configure admin when Django starts.
        This method is called when Django has finished loading all models.
        """
        # Import signal handlers
        from . import signals
        
        # Hide allauth models from admin interface
        self._hide_allauth_models()
        
        # Hide other unwanted models from admin interface  
        self._hide_unwanted_models()
    
    def _hide_allauth_models(self):
        """Hide allauth models from Django admin interface"""
        try:
            # Hide allauth account models
            from allauth.account.models import EmailAddress, EmailConfirmation
            if admin.site.is_registered(EmailAddress):
                admin.site.unregister(EmailAddress)
            if admin.site.is_registered(EmailConfirmation):
                admin.site.unregister(EmailConfirmation)
                
            # Hide allauth socialaccount models
            from allauth.socialaccount.models import SocialApp, SocialToken, SocialAccount
            if admin.site.is_registered(SocialApp):
                admin.site.unregister(SocialApp)
            if admin.site.is_registered(SocialToken):
                admin.site.unregister(SocialToken)
            if admin.site.is_registered(SocialAccount):
                admin.site.unregister(SocialAccount)
                
        except Exception as e:
            # Don't fail if allauth models aren't available
            print(f"Note: Could not unregister allauth models: {e}")
    
    def _hide_unwanted_models(self):
        """Hide other unwanted built-in models from Django admin interface"""
        try:
            # Hide Django Sites framework if not needed in admin
            from django.contrib.sites.models import Site
            if admin.site.is_registered(Site):
                admin.site.unregister(Site)
                
            # Hide Django Auth Groups if not actively used
            from django.contrib.auth.models import Group
            if admin.site.is_registered(Group):
                admin.site.unregister(Group)
                
            # Hide Wagtail models if not needed in Django admin (they have their own admin)
            try:
                from wagtail.documents.models import Document
                from wagtail.images.models import Image
                if admin.site.is_registered(Document):
                    admin.site.unregister(Document)
                if admin.site.is_registered(Image):
                    admin.site.unregister(Image)
            except ImportError:
                pass
                
            # Hide django-taggit tags if not actively managed in admin
            try:
                from taggit.models import Tag
                if admin.site.is_registered(Tag):
                    admin.site.unregister(Tag)
            except ImportError:
                pass
                
        except Exception as e:
            # Don't fail if models aren't available
            print(f"Note: Could not unregister some built-in models: {e}")