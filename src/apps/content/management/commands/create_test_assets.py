"""
Django management command to create test assets for API testing
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.content.models import Resource, Distribution
from apps.licensing.models import License
import json

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test assets for API testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            default='test@example.com',
            help='Email of the test user to create assets for'
        )
        parser.add_argument(
            '--password',
            default='testpass123',
            help='Password for the test user'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Remove existing test assets before creating new ones'
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        clean = options['clean']

        self.stdout.write(
            self.style.SUCCESS(f'Creating test assets for user: {email}')
        )

        # Clean existing test data if requested
        if clean:
            self.stdout.write('Cleaning existing test assets...')
            test_resources = Resource.objects.filter(
                title__endswith=' - Test'
            )
            count = test_resources.count()
            test_resources.delete()
            self.stdout.write(
                self.style.WARNING(f'Removed {count} existing test assets')
            )

        # Ensure test user exists
        test_user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': 'Test',
                'last_name': 'User',
                'is_active': True,
                'is_superuser': True,
                'is_staff': True
            }
        )
        
        if created:
            test_user.set_password(password)
            test_user.save()
            self.stdout.write(
                self.style.SUCCESS(f'Created test user: {email}')
            )
        else:
            # Update password in case it changed
            test_user.set_password(password)
            test_user.save()
            self.stdout.write(f'Using existing user: {email}')

        # Test assets data
        test_assets = [
            {
                'title': 'Quran Uthmani Script - Test',
                'description': 'Complete Quranic text in Uthmani script for API testing. This is a comprehensive dataset containing the full Quranic text.',
                'resource_type': 'text',
                'metadata': {
                    'pages': 604,
                    'verses': 6236,
                    'surahs': 114,
                    'test_data': True,
                    'api_testing': True
                }
            },
            {
                'title': 'Tafsir Ibn Katheer - Test',
                'description': 'Classical Quranic commentary by Ibn Katheer for API testing. A detailed interpretation and explanation of Quranic verses.',
                'resource_type': 'tafsir',
                'metadata': {
                    'volumes': 10,
                    'language': 'Arabic',
                    'author': 'Ibn Katheer',
                    'test_data': True,
                    'api_testing': True
                }
            },
            {
                'title': 'Recitation Al-Afasy - Test',
                'description': 'Complete Quranic recitation by Sheikh Mishary Al-Afasy for API testing. High-quality audio recording of the full Quran.',
                'resource_type': 'audio',
                'metadata': {
                    'duration': '18 hours',
                    'bitrate': '128 kbps',
                    'reciter': 'Sheikh Mishary Al-Afasy',
                    'test_data': True,
                    'api_testing': True
                }
            },
            {
                'title': 'Quran Translation English - Test',
                'description': 'English translation of the Quran for API testing. Clear and accessible translation for English-speaking users.',
                'resource_type': 'translation',
                'metadata': {
                    'translator': 'Test Translator',
                    'language': 'English',
                    'style': 'Modern',
                    'test_data': True,
                    'api_testing': True
                }
            },
            {
                'title': 'Tajweed Rules Guide - Test',
                'description': 'Comprehensive guide to Tajweed rules for API testing. Educational content about proper Quranic recitation.',
                'resource_type': 'text',
                'metadata': {
                    'category': 'Education',
                    'level': 'Beginner to Advanced',
                    'test_data': True,
                    'api_testing': True
                }
            }
        ]

        created_assets = []
        
        for i, asset_data in enumerate(test_assets):
            self.stdout.write(f"Creating asset: {asset_data['title']}")
            
            # Create resource
            resource, resource_created = Resource.objects.get_or_create(
                title=asset_data['title'],
                defaults={
                    'description': asset_data['description'],
                    'resource_type': asset_data['resource_type'],
                    'language': 'ar',
                    'version': '1.0.0',
                    'publisher': test_user,
                    'workflow_status': 'published',
                    'published_at': timezone.now(),
                    'metadata': asset_data['metadata'],
                    'checksum': f'test_checksum_{i}_{timezone.now().timestamp()}'
                }
            )
            
            if resource_created:
                self.stdout.write(f"  ✓ Created resource: {resource.id}")
                
                # Create distribution
                distribution, dist_created = Distribution.objects.get_or_create(
                    resource=resource,
                    format_type='ZIP',
                    version='1.0.0',
                    defaults={
                        'endpoint_url': f'https://cdn.example.com/downloads/{resource.title.lower().replace(" ", "-").replace("--", "-")}.zip',
                        'access_config': {
                            'rate_limit': {'requests_per_hour': 100},
                            'requires_api_key': False
                        },
                        'metadata': {
                            'file_size': f'{2 + i}.5 MB',
                            'format': 'json' if asset_data['resource_type'] in ['text', 'translation'] else 'zip',
                            'compression': 'gzip'
                        }
                    }
                )
                
                if dist_created:
                    self.stdout.write(f"  ✓ Created distribution: {distribution.format_type}")
                
                # Create license
                license_obj, license_created = License.objects.get_or_create(
                    resource=resource,
                    defaults={
                        'license_type': 'open',
                        'terms': 'This is test data released under CC0 - Public Domain. You may use it freely for testing and development purposes.',
                        'requires_approval': False,
                        'effective_from': timezone.now(),
                        'geographic_restrictions': {},
                        'usage_restrictions': {
                            'attribution_required': False,
                            'commercial_use': True,
                            'test_data_notice': 'This is test data for API testing purposes only.'
                        }
                    }
                )
                
                if license_created:
                    self.stdout.write(f"  ✓ Created license: {license_obj.license_type}")
                
                created_assets.append({
                    'id': str(resource.id),
                    'title': resource.title,
                    'type': resource.resource_type
                })
            else:
                self.stdout.write(f"  - Asset already exists: {resource.id}")
                created_assets.append({
                    'id': str(resource.id),
                    'title': resource.title,
                    'type': resource.resource_type
                })

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(f'✅ Successfully created/verified {len(created_assets)} test assets')
        )
        
        # Output asset IDs for script usage
        self.stdout.write('')
        self.stdout.write('Asset IDs (for script usage):')
        for asset in created_assets:
            self.stdout.write(f"  {asset['id']} - {asset['title']} ({asset['type']})")
        
        # Output JSON for programmatic usage
        self.stdout.write('')
        self.stdout.write('JSON Output:')
        self.stdout.write(json.dumps([asset['id'] for asset in created_assets], indent=2))
        
        return f"Created {len(created_assets)} test assets"
