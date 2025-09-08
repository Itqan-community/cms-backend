"""
Django Admin Cleanup Configuration for Itqan CMS
Additional cleanup that runs after all apps are loaded to ensure only custom models are visible
"""
from django.contrib import admin
from django.apps import apps


def cleanup_admin_models():
    """
    Final cleanup of Django admin to hide all third-party models
    This function should be called after all apps have loaded their admin configurations
    """
    
    # List of apps whose models we want to keep visible in admin
    CUSTOM_APPS = {
        'accounts',
        'content', 
        'licensing',
        'analytics',
        'api_keys',
        'mock_api',
        'core',
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
            print(f"Admin cleanup: Unregistered {model._meta.app_label}.{model._meta.model_name}")
        except admin.sites.NotRegistered:
            # Model was already unregistered, skip
            pass
        except Exception as e:
            print(f"Admin cleanup: Error unregistering {model._meta.app_label}.{model._meta.model_name}: {e}")
    
    print(f"Admin cleanup complete. {len(models_to_unregister)} third-party models hidden from admin.")


def get_admin_stats():
    """Get statistics about what's currently registered in admin"""
    registered_models = admin.site._registry.keys()
    
    stats = {}
    for model in registered_models:
        app_label = model._meta.app_label
        if app_label not in stats:
            stats[app_label] = []
        stats[app_label].append(model._meta.model_name)
    
    return stats


def print_admin_stats():
    """Print current admin registration statistics"""
    stats = get_admin_stats()
    print("\nCurrent Django Admin Model Registration:")
    print("=" * 50)
    for app_label, models in sorted(stats.items()):
        print(f"{app_label}:")
        for model_name in sorted(models):
            print(f"  - {model_name}")
    print("=" * 50)
    print(f"Total apps: {len(stats)}")
    print(f"Total models: {sum(len(models) for models in stats.values())}")
