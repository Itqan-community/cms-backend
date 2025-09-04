"""
Management command to ensure a superuser exists with correct password
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Ensure superuser exists with correct password'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Superuser email')
        parser.add_argument('--username', type=str, help='Superuser username')
        parser.add_argument('--password', type=str, help='Superuser password')
        parser.add_argument('--reset-password', action='store_true', 
                          help='Reset password even if user exists')

    def handle(self, *args, **options):
        # Get credentials from options or environment variables
        email = options.get('email') or os.environ.get('DJANGO_SUPERUSER_EMAIL')
        username = options.get('username') or os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        password = options.get('password') or os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not email or not password:
            self.stdout.write(
                self.style.ERROR('Email and password are required. '
                               'Provide via --email/--password or DJANGO_SUPERUSER_EMAIL/DJANGO_SUPERUSER_PASSWORD')
            )
            return

        # Try to get existing user
        try:
            user = User.objects.get(email=email)
            self.stdout.write(f'Found existing superuser: {user.email}')
            
            # Check if password needs to be reset
            if options.get('reset_password') or not user.check_password(password):
                user.set_password(password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Updated password for superuser: {user.email}')
                )
            else:
                self.stdout.write(f'Superuser password is already correct: {user.email}')
                
        except User.DoesNotExist:
            # Create new superuser
            self.stdout.write(f'Creating new superuser: {email}')
            
            # Get or create default admin role
            from apps.accounts.models import Role
            admin_role, created = Role.objects.get_or_create(
                name='Admin',
                defaults={
                    'description': 'Full system administrator access',
                    'permissions': Role.get_default_permissions('Admin')
                }
            )
            
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                first_name='Admin',
                last_name='User',
                role=admin_role,
                email_verified=True,
                auth_provider='email'
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created superuser: {user.email}')
            )

        # Verify the user has all required superuser attributes
        if not user.is_superuser or not user.is_staff or not user.is_active:
            user.is_superuser = True
            user.is_staff = True
            user.is_active = True
            user.save()
            self.stdout.write(
                self.style.WARNING(f'Fixed superuser flags for: {user.email}')
            )

        # Test authentication
        from django.contrib.auth import authenticate
        test_user = authenticate(email=email, password=password)
        if test_user:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Authentication test passed for: {email}')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'❌ Authentication test failed for: {email}')
            )
