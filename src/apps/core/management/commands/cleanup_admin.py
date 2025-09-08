"""
Django management command to clean up admin interface
Removes third-party models from Django admin, keeping only custom project models
"""
from django.core.management.base import BaseCommand
from django.contrib import admin
from django.apps import apps


class Command(BaseCommand):
    help = 'Clean up Django admin to show only custom project models'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--show-stats',
            action='store_true',
            help='Show current admin registration statistics',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be unregistered without actually doing it',
        )
    
    def handle(self, *args, **options):
        """Execute the admin cleanup"""
        
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
        
        if options['show_stats']:
            self.show_admin_stats()
            return
        
        # Get all currently registered models
        registered_models = list(admin.site._registry.keys())
        
        # Identify models to unregister (not from our custom apps)
        models_to_unregister = []
        for model in registered_models:
            app_label = model._meta.app_label
            if app_label not in CUSTOM_APPS:
                models_to_unregister.append(model)
        
        self.stdout.write(f"Found {len(models_to_unregister)} third-party models to hide from admin:")
        
        # Show what will be unregistered
        for model in models_to_unregister:
            self.stdout.write(f"  - {model._meta.app_label}.{model._meta.model_name}")
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING("Dry run mode - no changes made"))
            return
        
        # Unregister non-custom models
        unregistered_count = 0
        for model in models_to_unregister:
            try:
                admin.site.unregister(model)
                self.stdout.write(
                    self.style.SUCCESS(f"Unregistered {model._meta.app_label}.{model._meta.model_name}")
                )
                unregistered_count += 1
            except admin.sites.NotRegistered:
                # Model was already unregistered, skip
                self.stdout.write(
                    self.style.WARNING(f"Already unregistered: {model._meta.app_label}.{model._meta.model_name}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error unregistering {model._meta.app_label}.{model._meta.model_name}: {e}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"Admin cleanup complete. {unregistered_count} models hidden from admin.")
        )
        
        # Show final stats
        self.show_admin_stats()
    
    def show_admin_stats(self):
        """Show current admin registration statistics"""
        registered_models = admin.site._registry.keys()
        
        stats = {}
        for model in registered_models:
            app_label = model._meta.app_label
            if app_label not in stats:
                stats[app_label] = []
            stats[app_label].append(model._meta.model_name)
        
        self.stdout.write("\nCurrent Django Admin Model Registration:")
        self.stdout.write("=" * 50)
        for app_label, models in sorted(stats.items()):
            self.stdout.write(f"{app_label}:")
            for model_name in sorted(models):
                self.stdout.write(f"  - {model_name}")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Total apps: {len(stats)}")
        self.stdout.write(f"Total models: {sum(len(models) for models in stats.values())}")
