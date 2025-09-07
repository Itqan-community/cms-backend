"""
Django management command to create test assets for API testing
Usage: python manage.py create_test_assets --email test@example.com
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.content.models import Distribution
from apps.content.models import Resource
from apps.licensing.models import License

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test assets for API testing with "- Test" suffix'

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default="test@example.com",
            help="Email of the user to create assets for (default: test@example.com)",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Remove existing test assets before creating new ones",
        )

    def handle(self, *args, **options):
        email = options["email"]
        clean = options["clean"]

        self.stdout.write(
            self.style.SUCCESS(f"🚀 Creating test assets for user: {email}"),
        )

        # Clean existing test data if requested
        if clean:
            self.stdout.write("🧹 Cleaning existing test assets...")
            test_resources = Resource.objects.filter(title__endswith=" - Test")
            count = test_resources.count()
            test_resources.delete()
            self.stdout.write(
                self.style.WARNING(f"🗑️  Removed {count} existing test assets"),
            )

        # Find the user
        try:
            user = User.objects.get(email=email)
            self.stdout.write(f"✅ Found user: {user.email}")
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ User {email} not found!"),
            )
            return

        # Test assets data
        test_assets = [
            {
                "title": "Quran Uthmani Script - Test",
                "description": "Complete Quranic text in Uthmani script for API testing. This comprehensive dataset contains the full Quranic text in the traditional Uthmani script.",
                "resource_type": "text",
                "metadata": {
                    "pages": 604,
                    "verses": 6236,
                    "surahs": 114,
                    "script": "Uthmani",
                    "test_data": True,
                    "api_testing": True,
                },
            },
            {
                "title": "Tafsir Ibn Katheer - Test",
                "description": "Classical Quranic commentary by Ibn Katheer for API testing. A detailed interpretation and explanation of Quranic verses by the renowned scholar.",
                "resource_type": "tafsir",
                "metadata": {
                    "volumes": 10,
                    "language": "Arabic",
                    "author": "Ibn Katheer",
                    "period": "Classical",
                    "test_data": True,
                    "api_testing": True,
                },
            },
            {
                "title": "Recitation Al-Afasy - Test",
                "description": "Complete Quranic recitation by Sheikh Mishary Al-Afasy for API testing. High-quality audio recording of the full Quran by this renowned reciter.",
                "resource_type": "audio",
                "metadata": {
                    "duration": "18 hours",
                    "bitrate": "128 kbps",
                    "reciter": "Sheikh Mishary Al-Afasy",
                    "style": "Hafs",
                    "test_data": True,
                    "api_testing": True,
                },
            },
            {
                "title": "Quran Translation English - Test",
                "description": "English translation of the Quran for API testing. Clear and accessible translation for English-speaking users with modern language.",
                "resource_type": "translation",
                "metadata": {
                    "translator": "Test Translator",
                    "target_language": "English",
                    "style": "Modern",
                    "year": 2024,
                    "test_data": True,
                    "api_testing": True,
                },
            },
            {
                "title": "Tajweed Rules Guide - Test",
                "description": "Comprehensive guide to Tajweed rules for API testing. Educational content about proper Quranic recitation rules and techniques.",
                "resource_type": "text",
                "metadata": {
                    "category": "Education",
                    "level": "Beginner to Advanced",
                    "rules_count": 15,
                    "examples": True,
                    "test_data": True,
                    "api_testing": True,
                },
            },
        ]

        created_count = 0
        existing_count = 0

        for i, asset_data in enumerate(test_assets, 1):
            self.stdout.write(f"\n📦 {i}. Processing: {asset_data['title']}")

            try:
                # Create or get resource
                resource, created = Resource.objects.get_or_create(
                    title=asset_data["title"],
                    defaults={
                        "description": asset_data["description"],
                        "resource_type": asset_data["resource_type"],
                        "language": "ar",
                        "version": "1.0.0",
                        "publisher": user,
                        "workflow_status": "published",
                        "published_at": timezone.now(),
                        "metadata": asset_data["metadata"],
                        "checksum": f"test_checksum_{i}_{timezone.now().timestamp()}",
                    },
                )

                if created:
                    self.stdout.write(f"   ✅ Created resource: {resource.id}")
                    created_count += 1

                    # Create distribution
                    distribution, dist_created = Distribution.objects.get_or_create(
                        resource=resource,
                        format_type="ZIP",
                        version="1.0.0",
                        defaults={
                            "endpoint_url": f"https://cdn.example.com/downloads/{resource.title.lower().replace(' ', '-').replace('--', '-')}.zip",
                            "access_config": {
                                "rate_limit": {"requests_per_hour": 100},
                                "requires_api_key": False,
                                "download_limit": None,
                            },
                            "metadata": {
                                "file_size": f"{2 + i}.5 MB",
                                "format": "application/zip",
                                "compression": "gzip",
                                "checksum": f"dist_checksum_{i}",
                            },
                        },
                    )

                    if dist_created:
                        self.stdout.write(
                            f"   ✅ Created distribution: {distribution.format_type}",
                        )

                    # Create license
                    license_obj, license_created = License.objects.get_or_create(
                        resource=resource,
                        defaults={
                            "license_type": "open",
                            "terms": "This is test data released under CC0 - Public Domain. You may use it freely for testing and development purposes.",
                            "requires_approval": False,
                            "effective_from": timezone.now(),
                            "geographic_restrictions": {},
                            "usage_restrictions": {
                                "attribution_required": False,
                                "commercial_use": True,
                                "redistribution": True,
                                "test_data_notice": "This is test data for API testing purposes only.",
                            },
                        },
                    )

                    if license_created:
                        self.stdout.write(
                            f"   ✅ Created license: {license_obj.license_type}",
                        )

                else:
                    self.stdout.write(f"   i  Already exists: {resource.id}")
                    existing_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"   ❌ Error creating {asset_data['title']}: {e!s}",
                    ),
                )

        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            self.style.SUCCESS("🎉 Test Assets Creation Complete!"),
        )
        self.stdout.write("📊 Summary:")
        self.stdout.write(f"   • Created: {created_count} new assets")
        self.stdout.write(f"   • Existing: {existing_count} assets")
        self.stdout.write(
            f"   • Total: {created_count + existing_count} test assets available",
        )

        if created_count > 0:
            self.stdout.write("\n🔍 Verify your test data:")
            self.stdout.write(
                '   curl -s "https://develop.api.cms.itqan.dev/api/v1/assets/" | jq .',
            )
            self.stdout.write("   ./test_assets_api.sh --assets")

        self.stdout.write("\n✨ Test data is ready for API testing!")
