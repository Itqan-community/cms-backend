"""
Core Django Admin Configuration for Itqan CMS
Customizes the Django admin interface to show only project-specific models
"""

from django.apps import apps
from django.contrib import admin

# Import allauth models to unregister
try:
    from allauth.account.models import EmailAddress
    from allauth.account.models import EmailConfirmation
    from allauth.socialaccount.models import SocialAccount
    from allauth.socialaccount.models import SocialApp
    from allauth.socialaccount.models import SocialToken

    ALLAUTH_AVAILABLE = True
except ImportError:
    ALLAUTH_AVAILABLE = False

# Import wagtail models to unregister
try:
    from wagtail.documents.models import Document
    from wagtail.images.models import Image
    from wagtail.images.models import Rendition
    from wagtail.models import Page
    from wagtail.models import Site as WagtailSite
    from wagtail.snippets.models import register_snippet
    from wagtail.users.models import UserProfile

    WAGTAIL_AVAILABLE = True
except ImportError:
    WAGTAIL_AVAILABLE = False

# Import model translation models to unregister
try:
    from modeltranslation.models import ModelTranslation

    MODELTRANSLATION_AVAILABLE = True
except ImportError:
    MODELTRANSLATION_AVAILABLE = False

# Import taggit models to unregister
try:
    from taggit.models import Tag
    from taggit.models import TaggedItem

    TAGGIT_AVAILABLE = True
except ImportError:
    TAGGIT_AVAILABLE = False


class AdminConfig:
    """
    Configuration class to manage Django admin model visibility
    Only shows custom project models, hides third-party package models
    """

    # Define which apps contain our custom models that should be visible
    CUSTOM_APPS = [
        "accounts",
        "content",
        "licensing",
        "analytics",
        "search",
        "medialib",
        "api_keys",
        "mock_api",
        "core",
    ]

    # Models from Django's contrib apps that should be hidden
    DJANGO_MODELS_TO_HIDE = [
        ("auth", "Group"),
        ("auth", "Permission"),
        ("contenttypes", "ContentType"),
        ("sessions", "Session"),
        ("sites", "Site"),
        ("admin", "LogEntry"),
        ("messages", "Message"),
    ]

    # Allauth models to hide
    ALLAUTH_MODELS_TO_HIDE = [
        ("account", "EmailAddress"),
        ("account", "EmailConfirmation"),
        ("socialaccount", "SocialApp"),
        ("socialaccount", "SocialAccount"),
        ("socialaccount", "SocialToken"),
    ]

    # Wagtail models to hide
    WAGTAIL_MODELS_TO_HIDE = [
        ("wagtailcore", "Page"),
        ("wagtailcore", "Site"),
        ("wagtailusers", "UserProfile"),
        ("wagtailimages", "Image"),
        ("wagtailimages", "Rendition"),
        ("wagtaildocs", "Document"),
        ("wagtailforms", "FormSubmission"),
        ("wagtailredirects", "Redirect"),
        ("wagtailembeds", "Embed"),
        ("wagtailsearch", "Query"),
        ("wagtailsearch", "QueryDailyHits"),
    ]

    # Other third-party models to hide
    OTHER_MODELS_TO_HIDE = [
        ("taggit", "Tag"),
        ("taggit", "TaggedItem"),
    ]

    @classmethod
    def get_model_to_hide(cls, app_label, model_name):
        """Get model class if it exists and is registered"""
        try:
            model = apps.get_model(app_label, model_name)
            if model in admin.site._registry:
                return model
        except (LookupError, AttributeError):
            pass
        return None

    @classmethod
    def unregister_models(cls):
        """Unregister third-party models from Django admin"""
        models_to_unregister = []

        # Collect Django contrib models
        for app_label, model_name in cls.DJANGO_MODELS_TO_HIDE:
            model = cls.get_model_to_hide(app_label, model_name)
            if model:
                models_to_unregister.append(model)

        # Collect allauth models if available
        if ALLAUTH_AVAILABLE:
            for app_label, model_name in cls.ALLAUTH_MODELS_TO_HIDE:
                model = cls.get_model_to_hide(app_label, model_name)
                if model:
                    models_to_unregister.append(model)

        # Collect Wagtail models if available
        if WAGTAIL_AVAILABLE:
            for app_label, model_name in cls.WAGTAIL_MODELS_TO_HIDE:
                model = cls.get_model_to_hide(app_label, model_name)
                if model:
                    models_to_unregister.append(model)

        # Collect other third-party models
        for app_label, model_name in cls.OTHER_MODELS_TO_HIDE:
            model = cls.get_model_to_hide(app_label, model_name)
            if model:
                models_to_unregister.append(model)

        # Unregister all collected models
        for model in models_to_unregister:
            try:
                admin.site.unregister(model)
                # Unregistered model from admin
            except admin.sites.NotRegistered:
                # Model was not registered, skip
                pass
            except Exception as e:
                # Error unregistering model
                pass

    @classmethod
    def customize_admin_site(cls):
        """Customize the Django admin site"""
        admin.site.site_header = "Itqan CMS Administration"
        admin.site.site_title = "Itqan CMS Admin"
        admin.site.index_title = "Welcome to Itqan CMS Administration"
        admin.site.site_url = None  # Don't show "View Site" link


# Apply the admin configuration
def setup_admin():
    """Setup custom admin configuration"""
    AdminConfig.unregister_models()
    AdminConfig.customize_admin_site()


# Call setup when this module is imported
# Note: This will run when Django loads admin configurations
setup_admin()


# Additional cleanup to handle models registered after this module loads
def final_admin_cleanup():
    """Final cleanup that runs after all apps have loaded their admin configurations"""

    # List of apps whose models we want to keep visible in admin
    custom_apps = {
        "accounts",
        "content",
        "licensing",
        "analytics",
        "search",
        "medialib",
        "api_keys",
        "mock_api",
        "core",
    }

    # Get all currently registered models
    registered_models = list(admin.site._registry.keys())

    # Identify models to unregister (not from our custom apps)
    models_to_unregister = []
    for model in registered_models:
        app_label = model._meta.app_label
        if app_label not in CUSTOM_APPS:
            models_to_unregister.append(model)

    # Unregister non-custom models
    for model in models_to_unregister:
        try:
            admin.site.unregister(model)
            # Final cleanup: Unregistered model
        except admin.sites.NotRegistered:
            # Model was already unregistered, skip
            pass
        except Exception as e:
            # Final cleanup: Error unregistering model
            pass


# Export the cleanup function for use in other modules
__all__ = ["AdminConfig", "final_admin_cleanup", "setup_admin"]
