# Generated manually

from django.db import migrations


def create_default_roles(apps, schema_editor):
    """Create default roles for the CMS system"""
    Role = apps.get_model('accounts', 'Role')
    
    # Define default roles with their permissions
    default_roles = [
        {
            'name': 'Admin',
            'description': 'Full system access with user management capabilities',
            'permissions': {
                'users': ['create', 'read', 'update', 'delete'],
                'roles': ['create', 'read', 'update', 'delete'],
                'resources': ['create', 'read', 'update', 'delete', 'publish', 'review'],
                'licenses': ['create', 'read', 'update', 'delete', 'approve'],
                'distributions': ['create', 'read', 'update', 'delete'],
                'access_requests': ['read', 'approve', 'reject'],
                'usage_events': ['read'],
                'system': ['settings', 'logs', 'analytics']
            }
        },
        {
            'name': 'Publisher',
            'description': 'Content creation and publishing capabilities',
            'permissions': {
                'resources': ['create', 'read', 'update', 'delete', 'publish'],
                'licenses': ['create', 'read', 'update'],
                'distributions': ['create', 'read', 'update', 'delete'],
                'access_requests': ['read_own'],
                'usage_events': ['read_own']
            }
        },
        {
            'name': 'Developer',
            'description': 'API access for application development',
            'permissions': {
                'resources': ['read'],
                'distributions': ['read'],
                'access_requests': ['create', 'read_own'],
                'usage_events': ['read_own']
            }
        },
        {
            'name': 'Reviewer',
            'description': 'Content review and approval capabilities',
            'permissions': {
                'resources': ['read', 'review', 'approve'],
                'licenses': ['read', 'review'],
                'distributions': ['read']
            }
        }
    ]
    
    # Create roles if they don't exist
    for role_data in default_roles:
        Role.objects.get_or_create(
            name=role_data['name'],
            defaults={
                'description': role_data['description'],
                'permissions': role_data['permissions']
            }
        )


def reverse_default_roles(apps, schema_editor):
    """Remove default roles"""
    Role = apps.get_model('accounts', 'Role')
    default_role_names = ['Admin', 'Publisher', 'Developer', 'Reviewer']
    Role.objects.filter(name__in=default_role_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_roles, reverse_default_roles),
    ]
