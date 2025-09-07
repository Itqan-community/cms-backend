"""
Management command to create comprehensive test data that matches ERD relationships
"""

import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.content.models import Asset
from apps.content.models import AssetAccess
from apps.content.models import AssetAccessRequest
from apps.content.models import AssetVersion
from apps.content.models import Distribution
from apps.content.models import License
from apps.content.models import PublishingOrganization
from apps.content.models import PublishingOrganizationMember
from apps.content.models import Resource
from apps.content.models import ResourceVersion
from apps.content.models import UsageEvent

User = get_user_model()


class Command(BaseCommand):
    help = "Create comprehensive test data that demonstrates all ERD relationships"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help="Clear existing test data before creating new data",
        )
        parser.add_argument(
            "--minimal",
            action="store_true",
            help="Create minimal test data set",
        )
        parser.add_argument(
            "--large-dataset",
            action="store_true",
            help="Create large dataset for performance testing",
        )

    def handle(self, *args, **options):
        self.stdout.write("🌱 Starting comprehensive data seeding...")

        if options["clear_existing"]:
            self.clear_test_data()

        with transaction.atomic():
            if options["large_dataset"]:
                self.create_large_dataset()
            elif options["minimal"]:
                self.create_minimal_dataset()
            else:
                self.create_standard_dataset()

        self.stdout.write(self.style.SUCCESS("✅ Data seeding completed successfully!"))

    def clear_test_data(self):
        """Clear existing test data"""
        self.stdout.write("🧹 Clearing existing test data...")

        # Clear in reverse dependency order
        UsageEvent.objects.filter(developer_user__email__contains="@example.").delete()
        AssetAccess.all_objects.filter(user__email__contains="@example.").delete()
        AssetAccessRequest.objects.filter(
            developer_user__email__contains="@example.",
        ).delete()
        AssetVersion.objects.filter(asset__title__contains="Test").delete()
        Asset.objects.filter(title__contains="Test").delete()
        Distribution.objects.filter(resource__name__contains="Test").delete()
        ResourceVersion.objects.filter(resource__name__contains="Test").delete()
        Resource.objects.filter(name__contains="Test").delete()
        PublishingOrganizationMember.objects.filter(
            user__email__contains="@example.",
        ).delete()
        PublishingOrganization.objects.filter(name__contains="Test").delete()
        User.objects.filter(email__contains="@example.").delete()

        self.stdout.write("✅ Test data cleared")

    def create_minimal_dataset(self):
        """Create minimal test data set"""
        self.stdout.write("📦 Creating minimal dataset...")

        # Create 1 license, 1 user, 1 organization, 1 resource, 1 asset
        license_obj = self.create_test_license("cc0")
        user = self.create_test_user("minimal@example.com", "Test", "User")
        org = self.create_test_organization("Test Organization", user)
        resource = self.create_test_resource("Test Resource", org, license_obj)
        asset = self.create_test_asset("Test Asset", org, license_obj, resource)

        self.stdout.write("✅ Minimal dataset created")

    def create_standard_dataset(self):
        """Create standard comprehensive test data"""
        self.stdout.write("📚 Creating standard comprehensive dataset...")

        # Create licenses
        licenses = self.create_test_licenses()

        # Create users
        users = self.create_test_users()

        # Create organizations with memberships
        organizations = self.create_test_organizations(users)

        # Create resources and versions
        resources = self.create_test_resources(organizations, licenses)

        # Create assets and versions
        assets = self.create_test_assets(organizations, licenses, resources)

        # Create access requests and grants
        self.create_test_access_workflow(users, assets)

        # Create distributions
        self.create_test_distributions(resources)

        # Create usage events
        self.create_test_usage_events(users, assets, resources)

        self.stdout.write("✅ Standard dataset created")

    def create_large_dataset(self):
        """Create large dataset for performance testing"""
        self.stdout.write("🏋️ Creating large dataset for performance testing...")

        # Create base data
        licenses = self.create_test_licenses()

        # Create many users (100)
        users = []
        for i in range(100):
            user = self.create_test_user(
                f"user{i:03d}@example.com",
                f"User{i:03d}",
                "TestUser",
            )
            users.append(user)

        # Create many organizations (50)
        organizations = []
        for i in range(50):
            org = self.create_test_organization(
                f"Test Organization {i:02d}",
                random.choice(users),
            )
            organizations.append(org)

        # Create many resources (500)
        resources = []
        categories = ["mushaf", "tafsir", "recitation"]
        for i in range(500):
            resource = self.create_test_resource(
                f"Test Resource {i:03d}",
                random.choice(organizations),
                random.choice(licenses),
                category=random.choice(categories),
            )
            resources.append(resource)

        # Create many assets (1000)
        assets = []
        for i in range(1000):
            asset = self.create_test_asset(
                f"Test Asset {i:04d}",
                random.choice(organizations),
                random.choice(licenses),
                random.choice(resources),
            )
            assets.append(asset)

        # Create many usage events (10000)
        for i in range(10000):
            user = random.choice(users)
            asset = random.choice(assets)

            UsageEvent.objects.create(
                developer_user=user,
                usage_kind=random.choice(["view", "file_download", "api_access"]),
                subject_kind="asset",
                asset_id=asset.id,
                metadata={"test_event": True},
                ip_address=f"192.168.1.{random.randint(1, 254)}",
                user_agent="Test User Agent",
            )

        self.stdout.write("✅ Large dataset created")

    def create_test_licenses(self):
        """Create comprehensive test licenses"""
        licenses_data = [
            {
                "code": "cc0",
                "name": "CC0 - Public Domain",
                "short_name": "CC0",
                "is_default": True,
                "url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "summary": "No rights reserved - public domain",
                "license_terms": [
                    {
                        "title": "البند الأول",
                        "title_en": "First Term",
                        "description": "يحق لك نسخ وتعديل وتوزيع العمل",
                        "description_en": "You may copy, modify and distribute the work",
                        "order": 1,
                    },
                    {
                        "title": "البند الثاني",
                        "title_en": "Second Term",
                        "description": "لا يوجد ضمان للعمل",
                        "description_en": "No warranty for the work",
                        "order": 2,
                    },
                ],
                "permissions": [
                    {
                        "key": "commercial_use",
                        "label": "Commercial use",
                        "description": "You may use for commercial purposes",
                    },
                    {
                        "key": "modification",
                        "label": "Modification",
                        "description": "You may modify the work",
                    },
                    {
                        "key": "distribution",
                        "label": "Distribution",
                        "description": "You may distribute the work",
                    },
                ],
                "conditions": [],
                "limitations": [
                    {
                        "key": "no_warranty",
                        "label": "No warranty",
                        "description": "No warranty is provided",
                    },
                ],
            },
            {
                "code": "cc-by-4.0",
                "name": "Creative Commons Attribution 4.0",
                "short_name": "CC BY 4.0",
                "is_default": False,
                "url": "https://creativecommons.org/licenses/by/4.0/",
                "summary": "You may use with attribution",
                "license_terms": [
                    {
                        "title": "Attribution Required",
                        "description": "You must give appropriate credit",
                        "order": 1,
                    },
                ],
                "permissions": [
                    {
                        "key": "commercial_use",
                        "label": "Commercial use",
                        "description": "Commercial use allowed",
                    },
                    {
                        "key": "modification",
                        "label": "Modification",
                        "description": "Modification allowed",
                    },
                    {
                        "key": "distribution",
                        "label": "Distribution",
                        "description": "Distribution allowed",
                    },
                ],
                "conditions": [
                    {
                        "key": "include_copyright",
                        "label": "Include copyright",
                        "description": "Include copyright notice",
                    },
                    {
                        "key": "include_license",
                        "label": "Include license",
                        "description": "Include license text",
                    },
                ],
                "limitations": [
                    {
                        "key": "no_warranty",
                        "label": "No warranty",
                        "description": "No warranty provided",
                    },
                ],
            },
            {
                "code": "mit",
                "name": "MIT License",
                "short_name": "MIT",
                "is_default": False,
                "url": "https://opensource.org/licenses/MIT",
                "summary": "Permissive software license",
                "license_terms": [
                    {
                        "title": "Permission Notice",
                        "description": "Permission to use, copy, modify, and distribute",
                        "order": 1,
                    },
                ],
                "permissions": [
                    {
                        "key": "commercial_use",
                        "label": "Commercial use",
                        "description": "Commercial use allowed",
                    },
                    {
                        "key": "modification",
                        "label": "Modification",
                        "description": "Modification allowed",
                    },
                    {
                        "key": "distribution",
                        "label": "Distribution",
                        "description": "Distribution allowed",
                    },
                    {
                        "key": "private_use",
                        "label": "Private use",
                        "description": "Private use allowed",
                    },
                ],
                "conditions": [
                    {
                        "key": "include_copyright",
                        "label": "Include copyright",
                        "description": "Include copyright notice",
                    },
                    {
                        "key": "include_license",
                        "label": "Include license",
                        "description": "Include license text",
                    },
                ],
                "limitations": [
                    {
                        "key": "no_warranty",
                        "label": "No warranty",
                        "description": "No warranty provided",
                    },
                    {
                        "key": "no_liability",
                        "label": "No liability",
                        "description": "No liability assumed",
                    },
                ],
            },
        ]

        licenses = []
        for license_data in licenses_data:
            license_obj, created = License.objects.get_or_create(
                code=license_data["code"],
                defaults=license_data,
            )
            licenses.append(license_obj)
            if created:
                self.stdout.write(f"  ✅ Created license: {license_obj.name}")

        return licenses

    def create_test_license(self, code):
        """Create a single test license"""
        license_data = {
            "code": code,
            "name": f"{code.upper()} Test License",
            "short_name": code.upper(),
            "is_default": code == "cc0",
            "summary": f"Test license {code}",
        }

        license_obj, created = License.objects.get_or_create(
            code=code,
            defaults=license_data,
        )
        return license

    def create_test_users(self):
        """Create test users with different roles"""
        users_data = [
            {
                "email": "publisher@tafsircenter.org",
                "first_name": "Ahmed",
                "last_name": "AlTafsir",
                "job_title": "Content Director",
                "phone_number": "+966501234567",
                "bio": "Expert in Quranic studies and Islamic scholarship",
                "organization": "Tafsir Center",
                "location": "Riyadh, Saudi Arabia",
            },
            {
                "email": "developer@example.com",
                "first_name": "Sara",
                "last_name": "Developer",
                "job_title": "Software Engineer",
                "phone_number": "+1234567890",
                "bio": "Full-stack developer specializing in Islamic tech",
                "organization": "TechCorp",
                "location": "San Francisco, CA",
            },
            {
                "email": "researcher@university.edu",
                "first_name": "Dr. Mohammad",
                "last_name": "Scholar",
                "job_title": "Islamic Studies Professor",
                "phone_number": "+441234567890",
                "bio": "Academic researcher in Islamic texts and history",
                "organization": "Oxford University",
                "location": "Oxford, UK",
            },
        ]

        users = []
        for user_data in users_data:
            user, created = User.objects.get_or_create(
                email=user_data["email"],
                defaults={
                    "username": user_data["email"],
                    "first_name": user_data["first_name"],
                    "last_name": user_data["last_name"],
                    "job_title": user_data["job_title"],
                    "phone_number": user_data["phone_number"],
                    "bio": user_data["bio"],
                    "organization": user_data["organization"],
                    "location": user_data["location"],
                    "auth_provider": "email",
                    "email_verified": True,
                    "profile_completed": True,
                },
            )
            users.append(user)
            if created:
                user.set_password("testpass123")
                user.save()
                self.stdout.write(
                    f"  ✅ Created user: {user.get_full_name()} ({user.email})",
                )

        return users

    def create_test_user(self, email, first_name, last_name):
        """Create a single test user"""
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": first_name,
                "last_name": last_name,
                "job_title": "Test User",
                "auth_provider": "email",
                "email_verified": True,
                "profile_completed": True,
            },
        )
        if created:
            user.set_password("testpass123")
            user.save()
        return user

    def create_test_organizations(self, users):
        """Create test publishing organizations"""
        organizations_data = [
            {
                "name": "Tafsir Center",
                "slug": "tafsir-center",
                "summary": "Dedicated to preserving and sharing Quranic knowledge through scholarly research and digital resources",
                "description": "A comprehensive center for Quranic interpretation and Islamic scholarship, providing authentic and reliable sources for students and researchers worldwide.",
                "bio": "Established by leading Islamic scholars to bridge traditional scholarship with modern technology.",
                "icone_image_url": "https://example.com/tafsir-center-logo.png",
                "contact_email": "contact@tafsircenter.org",
                "website": "https://tafsircenter.org",
                "location": "Riyadh, Saudi Arabia",
                "verified": True,
                "social_links": {
                    "twitter": "@TafsirCenter",
                    "youtube": "TafsirCenterTV",
                    "telegram": "tafsircenter",
                },
            },
            {
                "name": "Quran Foundation",
                "slug": "quran-foundation",
                "summary": "Global organization dedicated to Quranic studies and research",
                "description": "International foundation promoting understanding of the Quran through academic research, educational programs, and digital preservation.",
                "bio": "Founded to make Quranic knowledge accessible to all humanity.",
                "icone_image_url": "https://example.com/quran-foundation-logo.png",
                "contact_email": "info@quranfoundation.org",
                "website": "https://quranfoundation.org",
                "location": "Istanbul, Turkey",
                "verified": True,
                "social_links": {
                    "twitter": "@QuranFoundation",
                    "instagram": "quranfoundation",
                },
            },
            {
                "name": "Digital Islamic Library",
                "slug": "digital-islamic-library",
                "summary": "Digitizing and preserving Islamic texts for future generations",
                "description": "Specialized in converting traditional Islamic manuscripts into digital formats while maintaining academic integrity and authenticity.",
                "bio": "Technology meets tradition in preserving Islamic heritage.",
                "icone_image_url": "https://example.com/digital-library-logo.png",
                "contact_email": "library@islamicdigital.org",
                "website": "https://islamicdigital.org",
                "location": "Kuala Lumpur, Malaysia",
                "verified": False,
                "social_links": {
                    "github": "digital-islamic-library",
                    "twitter": "@IslamicDigital",
                },
            },
        ]

        organizations = []
        for i, org_data in enumerate(organizations_data):
            org, created = PublishingOrganization.objects.get_or_create(
                slug=org_data["slug"],
                defaults=org_data,
            )
            organizations.append(org)

            if created:
                self.stdout.write(f"  ✅ Created organization: {org.name}")

                # Create membership for the corresponding user
                if i < len(users):
                    PublishingOrganizationMember.objects.get_or_create(
                        user=users[i],
                        publishing_organization=org,
                        defaults={"role": "owner"},
                    )
                    self.stdout.write(
                        f"    📝 Added {users[i].get_full_name()} as owner",
                    )

        return organizations

    def create_test_organization(self, name, owner_user):
        """Create a single test organization"""
        slug = name.lower().replace(" ", "-")

        org, created = PublishingOrganization.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "summary": f"Test organization: {name}",
                "description": "This is a test organization created for development purposes.",
                "bio": f"Test bio for {name}",
                "verified": False,
            },
        )

        if created:
            # Add owner membership
            PublishingOrganizationMember.objects.get_or_create(
                user=owner_user,
                publishing_organization=org,
                defaults={"role": "owner"},
            )

        return org

    def create_test_resources(self, organizations, licenses):
        """Create test resources with versions"""
        resources_data = [
            {
                "name": "Tafsir Ibn Katheer Complete",
                "slug": "tafsir-ibn-katheer-complete",
                "description": "Complete commentary on the Quran by Ibn Katheer, one of the most respected classical interpretations",
                "description_en": "Complete commentary on the Quran by Ibn Katheer, one of the most respected classical interpretations",
                "description_ar": "تفسير القرآن الكريم كاملاً للإمام ابن كثير، من أهم التفاسير الكلاسيكية المعتمدة",
                "category": "tafsir",
                "status": "published",
                "organization_index": 0,  # Tafsir Center
                "license_index": 0,  # CC0
                "versions": [
                    {
                        "semvar": "1.0.0",
                        "type": "release",
                        "storage_url": "https://s3.example.com/tafsir-ibn-katheer-v1-0-0.zip",
                        "size_bytes": 52428800,  # 50 MB
                        "is_latest": True,
                        "summary": "First complete digital release",
                    },
                    {
                        "semvar": "0.9.0",
                        "type": "beta",
                        "storage_url": "https://s3.example.com/tafsir-ibn-katheer-v0-9-0.zip",
                        "size_bytes": 48000000,  # 45.8 MB
                        "is_latest": False,
                        "summary": "Beta release for testing",
                    },
                ],
            },
            {
                "name": "Mushaf Uthmani Text",
                "slug": "mushaf-uthmani-text",
                "description": "Complete Quranic text in Uthmani script with proper diacritics and formatting",
                "description_en": "Complete Quranic text in Uthmani script with proper diacritics and formatting",
                "description_ar": "النص القرآني الكامل بالرسم العثماني مع الضبط والتشكيل الصحيح",
                "category": "mushaf",
                "status": "published",
                "organization_index": 1,  # Quran Foundation
                "license_index": 0,  # CC0
                "versions": [
                    {
                        "semvar": "2.1.0",
                        "type": "release",
                        "storage_url": "https://s3.example.com/mushaf-uthmani-v2-1-0.zip",
                        "size_bytes": 15728640,  # 15 MB
                        "is_latest": True,
                        "summary": "Updated with improved diacritics",
                    },
                ],
            },
            {
                "name": "Quran Recitation Collection",
                "slug": "quran-recitation-collection",
                "description": "High-quality audio recordings of complete Quran recitations by renowned qaris",
                "description_en": "High-quality audio recordings of complete Quran recitations by renowned qaris",
                "description_ar": "تسجيلات صوتية عالية الجودة لتلاوات كاملة للقرآن الكريم من قراء مشهورين",
                "category": "recitation",
                "status": "published",
                "organization_index": 2,  # Digital Islamic Library
                "license_index": 1,  # CC BY 4.0
                "versions": [
                    {
                        "semvar": "1.2.0",
                        "type": "release",
                        "storage_url": "https://s3.example.com/recitation-collection-v1-2-0.zip",
                        "size_bytes": 2147483648,  # 2 GB
                        "is_latest": True,
                        "summary": "Added new qaris and improved audio quality",
                    },
                ],
            },
        ]

        resources = []
        for resource_data in resources_data:
            org = organizations[resource_data["organization_index"]]
            license_obj = licenses[resource_data["license_index"]]

            resource, created = Resource.objects.get_or_create(
                slug=resource_data["slug"],
                defaults={
                    "name": resource_data["name"],
                    "description": resource_data["description"],
                    "description_en": resource_data["description_en"],
                    "description_ar": resource_data["description_ar"],
                    "category": resource_data["category"],
                    "status": resource_data["status"],
                    "publishing_organization": org,
                    "default_license": license_obj,
                },
            )
            resources.append(resource)

            if created:
                self.stdout.write(f"  ✅ Created resource: {resource.name}")

                # Create versions
                for version_data in resource_data["versions"]:
                    ResourceVersion.objects.get_or_create(
                        resource=resource,
                        semvar=version_data["semvar"],
                        defaults=version_data,
                    )
                    self.stdout.write(f"    📦 Added version: {version_data['semvar']}")

        return resources

    def create_test_resource(self, name, organization, license_obj, category="tafsir"):
        """Create a single test resource"""
        slug = name.lower().replace(" ", "-")

        resource, created = Resource.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": f"Test resource: {name}",
                "category": category,
                "status": "published",
                "publishing_organization": organization,
                "default_license": license_obj,
            },
        )

        if created:
            # Create a version
            ResourceVersion.objects.get_or_create(
                resource=resource,
                semvar="1.0.0",
                defaults={
                    "type": "release",
                    "storage_url": f"https://s3.example.com/{slug}-v1-0-0.zip",
                    "size_bytes": 10485760,  # 10 MB
                    "is_latest": True,
                    "summary": "Initial test release",
                },
            )

        return resource

    def create_test_assets(self, organizations, licenses, resources):
        """Create test assets extracted from resources"""
        assets_data = [
            {
                "title": "Tafsir Ibn Katheer - JSON Format",
                "name": "tafsir-ibn-katheer-json",
                "description": "Complete tafsir in structured JSON format with verse-by-verse commentary",
                "long_description": "This dataset contains the complete Tafsir Ibn Katheer in a structured JSON format, making it easy to integrate into applications. Each verse is accompanied by its corresponding commentary, properly tagged and indexed.",
                "category": "tafsir",
                "format": "json",
                "encoding": "utf-8",
                "file_size": "25.5 MB",
                "version": "1.0.0",
                "language": "ar",
                "thumbnail_url": "https://example.com/tafsir-ibn-katheer-thumb.jpg",
                "organization_index": 0,
                "license_index": 0,
                "resource_index": 0,
                "download_count": 1543,
                "view_count": 8721,
            },
            {
                "title": "Mushaf Text - XML Format",
                "name": "mushaf-uthmani-xml",
                "description": "Complete Quranic text in structured XML with proper markup",
                "long_description": "Uthmani script Quranic text formatted as XML with detailed markup for verses, chapters, pages, and diacritical marks. Perfect for applications requiring precise text rendering.",
                "category": "mushaf",
                "format": "xml",
                "encoding": "utf-8",
                "file_size": "8.2 MB",
                "version": "2.1.0",
                "language": "ar",
                "thumbnail_url": "https://example.com/mushaf-xml-thumb.jpg",
                "organization_index": 1,
                "license_index": 0,
                "resource_index": 1,
                "download_count": 892,
                "view_count": 3456,
            },
            {
                "title": "Recitation Audio - MP3 Collection",
                "name": "recitation-mp3-collection",
                "description": "High-quality MP3 audio files of complete Quran recitation",
                "long_description": "Professional recordings of complete Quran recitation in high-quality MP3 format. Each surah is provided as a separate file with consistent audio levels and crystal-clear pronunciation.",
                "category": "recitation",
                "format": "mp3",
                "encoding": "mp3",
                "file_size": "450.8 MB",
                "version": "1.2.0",
                "language": "ar",
                "thumbnail_url": "https://example.com/recitation-mp3-thumb.jpg",
                "organization_index": 2,
                "license_index": 1,
                "resource_index": 2,
                "download_count": 2718,
                "view_count": 12043,
            },
        ]

        assets = []
        for asset_data in assets_data:
            org = organizations[asset_data["organization_index"]]
            license_obj = licenses[asset_data["license_index"]]
            resource = resources[asset_data["resource_index"]]

            asset, created = Asset.objects.get_or_create(
                name=asset_data["name"],
                defaults={
                    "title": asset_data["title"],
                    "description": asset_data["description"],
                    "long_description": asset_data["long_description"],
                    "category": asset_data["category"],
                    "format": asset_data["format"],
                    "encoding": asset_data["encoding"],
                    "file_size": asset_data["file_size"],
                    "version": asset_data["version"],
                    "language": asset_data["language"],
                    "thumbnail_url": asset_data["thumbnail_url"],
                    "publishing_organization": org,
                    "license": license_obj,
                    "download_count": asset_data["download_count"],
                    "view_count": asset_data["view_count"],
                },
            )
            assets.append(asset)

            if created:
                self.stdout.write(f"  ✅ Created asset: {asset.title}")

                # Create asset version linking to resource version
                resource_version = resource.get_latest_version()
                if resource_version:
                    AssetVersion.objects.get_or_create(
                        asset=asset,
                        resource_version=resource_version,
                        defaults={
                            "name": asset.title,
                            "summary": f"Extracted from {resource.name} v{resource_version.semvar}",
                            "file_url": f"https://s3.example.com/assets/{asset.name}.{asset.format}",
                            "size_bytes": asset.size_bytes,
                        },
                    )
                    self.stdout.write(
                        f"    🔗 Linked to {resource.name} v{resource_version.semvar}",
                    )

        return assets

    def create_test_asset(self, title, organization, license_obj, resource):
        """Create a single test asset"""
        name = title.lower().replace(" ", "-").replace(",", "")

        asset, created = Asset.objects.get_or_create(
            name=name,
            defaults={
                "title": title,
                "description": f"Test asset: {title}",
                "category": resource.category,
                "format": "json",
                "file_size": "1.5 MB",
                "version": "1.0.0",
                "publishing_organization": organization,
                "license": license_obj,
                "download_count": random.randint(10, 100),
                "view_count": random.randint(50, 500),
            },
        )

        if created:
            # Create asset version
            resource_version = resource.get_latest_version()
            if resource_version:
                AssetVersion.objects.get_or_create(
                    asset=asset,
                    resource_version=resource_version,
                    defaults={
                        "name": asset.title,
                        "summary": f"Test asset extracted from {resource.name}",
                        "file_url": f"https://s3.example.com/test-assets/{name}.json",
                        "size_bytes": asset.size_bytes,
                    },
                )

        return asset

    def create_test_access_workflow(self, users, assets):
        """Create test access requests and grants"""
        self.stdout.write("🔐 Creating access workflow data...")

        # Create various access scenarios
        access_scenarios = [
            {
                "user_index": 1,  # developer@example.com
                "asset_index": 0,  # Tafsir JSON
                "purpose": "Academic research on Quranic interpretation patterns",
                "intended_use": "non-commercial",
                "status": "approved",
            },
            {
                "user_index": 2,  # researcher@university.edu
                "asset_index": 1,  # Mushaf XML
                "purpose": "Developing digital Mushaf application for students",
                "intended_use": "non-commercial",
                "status": "approved",
            },
            {
                "user_index": 1,  # developer@example.com
                "asset_index": 2,  # Recitation MP3
                "purpose": "Building mobile app for Quran learning",
                "intended_use": "commercial",
                "status": "approved",
            },
        ]

        for scenario in access_scenarios:
            user = users[scenario["user_index"]]
            asset = assets[scenario["asset_index"]]

            # Create access request
            access_request, created = AssetAccessRequest.objects.get_or_create(
                developer_user=user,
                asset=asset,
                defaults={
                    "developer_access_reason": scenario["purpose"],
                    "intended_use": scenario["intended_use"],
                    "status": scenario["status"],
                    "approved_at": timezone.now() if scenario["status"] == "approved" else None,
                    "approved_by": users[0] if scenario["status"] == "approved" else None,
                    "admin_response": "Approved for research purposes" if scenario["status"] == "approved" else "",
                },
            )

            if created and scenario["status"] == "approved":
                # Create access grant
                AssetAccess.all_objects.get_or_create(
                    asset_access_request=access_request,
                    defaults={
                        "user": user,
                        "asset": asset,
                        "effective_license": asset.license,
                        "granted_at": timezone.now(),
                        "expires_at": timezone.now() + timezone.timedelta(days=365),  # 1 year access
                        "download_url": f"https://secure.example.com/download/{asset.id}?token=abc123",
                    },
                )
                self.stdout.write(
                    f"  ✅ Created access: {user.get_full_name()} → {asset.title}",
                )

    def create_test_distributions(self, resources):
        """Create test distribution channels"""
        self.stdout.write("📡 Creating distribution channels...")

        distribution_examples = [
            {
                "resource_index": 0,  # Tafsir Ibn Katheer
                "format_type": "rest_api",
                "endpoint_url": "https://api.example.com/v1/tafsir/ibn-katheer",
                "version": "1.0.0",
                "access_config": {
                    "method": "GET",
                    "authentication": "api_key",
                    "rate_limit": "1000/hour",
                },
            },
            {
                "resource_index": 1,  # Mushaf Text
                "format_type": "direct_download",
                "endpoint_url": "https://cdn.example.com/mushaf/uthmani.zip",
                "version": "2.1.0",
                "access_config": {
                    "method": "GET",
                    "authentication": "none",
                },
            },
            {
                "resource_index": 2,  # Recitation Collection
                "format_type": "streaming",
                "endpoint_url": "https://stream.example.com/recitation/playlist.m3u8",
                "version": "1.2.0",
                "access_config": {
                    "method": "GET",
                    "authentication": "bearer_token",
                    "streaming_protocol": "HLS",
                },
            },
        ]

        for dist_data in distribution_examples:
            resource = resources[dist_data["resource_index"]]

            Distribution.objects.get_or_create(
                resource=resource,
                format_type=dist_data["format_type"],
                version=dist_data["version"],
                defaults={
                    "endpoint_url": dist_data["endpoint_url"],
                    "access_config": dist_data["access_config"],
                    "metadata": {
                        "created_for_testing": True,
                        "sample_distribution": True,
                    },
                },
            )
            self.stdout.write(
                f"  ✅ Created distribution: {resource.name} → {dist_data['format_type']}",
            )

    def create_test_usage_events(self, users, assets, resources):
        """Create realistic usage events for analytics"""
        self.stdout.write("📊 Creating usage events for analytics...")

        # Create diverse usage patterns
        event_patterns = [
            # Asset downloads
            {
                "user_index": 1,
                "asset_index": 0,
                "usage_kind": "file_download",
                "count": 5,
            },
            {
                "user_index": 2,
                "asset_index": 1,
                "usage_kind": "file_download",
                "count": 3,
            },
            {
                "user_index": 1,
                "asset_index": 2,
                "usage_kind": "file_download",
                "count": 2,
            },
            # Asset views
            {"user_index": 1, "asset_index": 0, "usage_kind": "view", "count": 12},
            {"user_index": 2, "asset_index": 0, "usage_kind": "view", "count": 8},
            {"user_index": 2, "asset_index": 1, "usage_kind": "view", "count": 6},
            {"user_index": 1, "asset_index": 2, "usage_kind": "view", "count": 4},
            # API access
            {
                "user_index": 1,
                "resource_index": 0,
                "usage_kind": "api_access",
                "count": 25,
            },
            {
                "user_index": 2,
                "resource_index": 1,
                "usage_kind": "api_access",
                "count": 15,
            },
        ]

        for pattern in event_patterns:
            user = users[pattern["user_index"]]

            for i in range(pattern["count"]):
                # Create event with some time variation
                created_at = timezone.now() - timezone.timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                )

                event_data = {
                    "developer_user": user,
                    "usage_kind": pattern["usage_kind"],
                    "ip_address": f"192.168.1.{random.randint(1, 254)}",
                    "user_agent": "Mozilla/5.0 (Test Browser)",
                    "created_at": created_at,
                }

                if "asset_index" in pattern:
                    asset = assets[pattern["asset_index"]]
                    event_data.update(
                        {
                            "subject_kind": "asset",
                            "asset_id": asset.id,
                            "metadata": {
                                "asset_title": asset.title,
                                "asset_format": asset.format,
                                "file_size": asset.file_size,
                            },
                        },
                    )
                elif "resource_index" in pattern:
                    resource = resources[pattern["resource_index"]]
                    event_data.update(
                        {
                            "subject_kind": "resource",
                            "resource_id": resource.id,
                            "metadata": {
                                "resource_name": resource.name,
                                "api_endpoint": f"/api/v1/resources/{resource.id}",
                            },
                        },
                    )

                UsageEvent.objects.create(**event_data)

        total_events = sum(p["count"] for p in event_patterns)
        self.stdout.write(f"  ✅ Created {total_events} usage events")
