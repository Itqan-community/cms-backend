"""
Django management command to create default roles and permissions for Itqan CMS
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.accounts.models import Role


class Command(BaseCommand):
    help = 'Create default roles and permissions for Itqan CMS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing roles with new permissions',
        )

    def handle(self, *args, **options):
        update_existing = options['update']
        
        roles_data = [
            {
                'name': 'Admin',
                'description': 'System administrator with full access to all features, user management, and system configuration.',
                'permissions': {
                    'users': ['create', 'read', 'update', 'delete'],
                    'roles': ['create', 'read', 'update', 'delete'],
                    'resources': ['create', 'read', 'update', 'delete'],
                    'licenses': ['create', 'read', 'update', 'delete'],
                    'distributions': ['create', 'read', 'update', 'delete'],
                    'access_requests': ['read', 'update', 'approve', 'reject'],
                    'usage_events': ['read'],
                    'system': ['admin_panel', 'system_settings', 'backup', 'restore'],
                    'workflow': ['manage', 'override'],
                    'media': ['upload', 'manage', 'delete'],
                    'search': ['configure', 'reindex', 'manage'],
                }
            },
            {
                'name': 'Publisher',
                'description': 'Islamic content publisher who can create, manage, and submit Quranic resources for review.',
                'permissions': {
                    'resources': ['create', 'read', 'update', 'submit_for_review'],
                    'licenses': ['create', 'read', 'update'],
                    'distributions': ['create', 'read', 'update'],
                    'usage_events': ['read_own'],
                    'workflow': ['submit', 'draft'],
                    'media': ['upload', 'manage_own'],
                    'access_requests': ['read_own_content'],
                }
            },
            {
                'name': 'Developer',
                'description': 'API consumer who can browse published content and request access to resources.',
                'permissions': {
                    'resources': ['read_published'],
                    'distributions': ['read_published'],
                    'access_requests': ['create', 'read_own'],
                    'usage_events': ['read_own'],
                    'api': ['access', 'generate_keys'],
                    'licenses': ['read_published', 'accept'],
                }
            },
            {
                'name': 'Reviewer',
                'description': 'Islamic scholar or content reviewer who can approve, reject, and publish Quranic content.',
                'permissions': {
                    'resources': ['read', 'review', 'approve', 'reject', 'publish'],
                    'licenses': ['read', 'review'],
                    'distributions': ['read'],
                    'workflow': ['review', 'approve', 'reject', 'publish'],
                    'access_requests': ['read', 'approve', 'reject'],
                    'usage_events': ['read'],
                }
            }
        ]

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for role_data in roles_data:
                role, created = Role.objects.get_or_create(
                    name=role_data['name'],
                    defaults={
                        'description': role_data['description'],
                        'permissions': role_data['permissions']
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created role: {role.name}')
                    )
                elif update_existing:
                    role.description = role_data['description']
                    role.permissions = role_data['permissions']
                    role.save()
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f'↻ Updated role: {role.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.NOTICE(f'- Role already exists: {role.name}')
                    )

        # Summary
        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Command completed successfully')
        )
        
        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'  • {created_count} roles created')
            )
        
        if updated_count > 0:
            self.stdout.write(
                self.style.WARNING(f'  • {updated_count} roles updated')
            )

        if not update_existing and Role.objects.count() > created_count:
            self.stdout.write(
                self.style.NOTICE(f'  • {Role.objects.count() - created_count} existing roles unchanged')
            )
            self.stdout.write(
                self.style.NOTICE(f'    Use --update flag to update existing roles')
            )

        # Display role summary
        self.stdout.write(f'\n📋 Role Summary:')
        for role in Role.objects.filter(is_active=True).order_by('name'):
            self.stdout.write(f'  • {role.name}: {len(role.permissions)} permission categories')
