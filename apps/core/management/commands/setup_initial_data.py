"""
Management command to set up initial data for Itqan CMS
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Set up initial data for Itqan CMS (roles, test users)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-superuser",
            action="store_true",
            help="Create a superuser admin account",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("🚀 Setting up initial data for Itqan CMS..."),
        )

        with transaction.atomic():
            # Create roles
            self.create_roles()

            # Create superuser if requested
            if options["create_superuser"]:
                self.create_superuser()

        self.stdout.write(
            self.style.SUCCESS("✅ Initial data setup completed successfully!"),
        )

    def create_roles(self):
        """Create the four main roles for Itqan CMS"""
        self.stdout.write("Creating roles...")

        roles_data = [
            {
                "name": "Admin",
                "description": "System administrators with full access to all features and user management.",
                "permissions": Role.get_default_permissions("Admin"),
            },
            {
                "name": "Publisher",
                "description": "Islamic organizations and content creators who publish Quranic resources.",
                "permissions": Role.get_default_permissions("Publisher"),
            },
            {
                "name": "Developer",
                "description": "App developers and API consumers who request access to Quranic content.",
                "permissions": Role.get_default_permissions("Developer"),
            },
            {
                "name": "Reviewer",
                "description": "Islamic scholars and QA team who review and approve content quality.",
                "permissions": Role.get_default_permissions("Reviewer"),
            },
        ]

        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data["name"],
                defaults={
                    "description": role_data["description"],
                    "permissions": role_data["permissions"],
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created role: {role.name}"),
                )
            else:
                # Update permissions if role already exists
                role.permissions = role_data["permissions"]
                role.save()
                self.stdout.write(
                    self.style.WARNING(f"  ↻ Updated role: {role.name}"),
                )

    def create_superuser(self):
        """Create a superuser admin account"""
        self.stdout.write("Creating superuser admin account...")

        # Get Admin role
        try:
            admin_role = Role.objects.get(name="Admin")
        except Role.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    "❌ Admin role not found. Please run without --create-superuser first.",
                ),
            )
            return

        # Check if superuser already exists
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.WARNING("⚠️  Superuser already exists. Skipping creation."),
            )
            return

        # Get superuser details
        email = input("Email: ").strip()
        if not email:
            self.stdout.write(
                self.style.ERROR("❌ Email is required."),
            )
            return

        first_name = input("First name: ").strip()
        last_name = input("Last name: ").strip()
        username = input("Username (optional): ").strip() or email.split("@")[0]

        # Create superuser
        user = User.objects.create_superuser(
            email=email,
            username=username,
            password=None,  # Will prompt for password
            first_name=first_name,
            last_name=last_name,
            role=admin_role,
        )

        # Set password
        password = input("Password: ")
        user.set_password(password)
        user.save()

        self.stdout.write(
            self.style.SUCCESS(f"✅ Created superuser: {user.email}"),
        )

    def create_test_data(self):
        """Create test data for development"""
        self.stdout.write("Creating test data...")

        # This can be expanded to create test resources, licenses, etc.
        # For now, we'll keep it simple with just roles

        self.stdout.write(
            self.style.SUCCESS("✅ Test data created successfully!"),
        )
