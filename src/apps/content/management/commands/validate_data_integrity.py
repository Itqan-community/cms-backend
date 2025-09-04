"""
Management command to validate ERD relationship integrity and data quality
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, F
from django.core.exceptions import ValidationError

from apps.content.models import (
    PublishingOrganization, PublishingOrganizationMember, License, Resource, 
    ResourceVersion, Asset, AssetVersion, AssetAccessRequest, AssetAccess, 
    UsageEvent, Distribution
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Validate data integrity and ERD relationship compliance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-issues',
            action='store_true',
            help='Attempt to fix found issues automatically',
        )
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='Show detailed information about each check',
        )
    
    def handle(self, *args, **options):
        self.fix_issues = options['fix_issues']
        self.detailed = options['detailed']
        
        self.stdout.write('🔍 Starting data integrity validation...')
        
        self.issues_found = 0
        self.issues_fixed = 0
        
        # Run all validation checks
        self.validate_user_data()
        self.validate_organizations()
        self.validate_licenses()
        self.validate_resources()
        self.validate_assets()
        self.validate_access_control()
        self.validate_usage_events()
        self.validate_distributions()
        self.validate_relationships()
        
        # Summary
        if self.issues_found == 0:
            self.stdout.write(self.style.SUCCESS('✅ All data integrity checks passed!'))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  Found {self.issues_found} issues'
                    + (f', fixed {self.issues_fixed}' if self.fix_issues else '')
                )
            )
    
    def log_issue(self, message, fix_action=None):
        """Log an issue and optionally fix it"""
        self.issues_found += 1
        self.stdout.write(self.style.ERROR(f'❌ {message}'))
        
        if self.fix_issues and fix_action:
            try:
                fix_action()
                self.issues_fixed += 1
                self.stdout.write(self.style.SUCCESS(f'   ✅ Fixed: {message}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Fix failed: {e}'))
    
    def validate_user_data(self):
        """Validate User model data quality"""
        self.stdout.write('\n👤 Validating User data...')
        
        # Check for users without names
        nameless_users = User.objects.filter(
            Q(first_name='') | Q(last_name='')
        )
        
        if nameless_users.exists():
            self.log_issue(
                f'{nameless_users.count()} users missing first_name or last_name',
                lambda: nameless_users.update(
                    first_name='Unknown',
                    last_name='User'
                )
            )
        
        # Check for unverified email addresses
        unverified_users = User.objects.filter(email_verified=False)
        if unverified_users.exists() and self.detailed:
            self.stdout.write(f'   ℹ️  {unverified_users.count()} users with unverified emails')
        
        # Check for incomplete profiles
        incomplete_profiles = User.objects.filter(profile_completed=False)
        if incomplete_profiles.exists() and self.detailed:
            self.stdout.write(f'   ℹ️  {incomplete_profiles.count()} users with incomplete profiles')
        
        self.stdout.write('   ✅ User validation complete')
    
    def validate_organizations(self):
        """Validate PublishingOrganization data"""
        self.stdout.write('\n🏢 Validating Publishing Organizations...')
        
        # Check for organizations without members
        orgs_without_members = PublishingOrganization.objects.annotate(
            member_count=Count('members')
        ).filter(member_count=0)
        
        if orgs_without_members.exists():
            self.log_issue(f'{orgs_without_members.count()} organizations have no members')
        
        # Check for organizations without owners
        orgs_without_owners = PublishingOrganization.objects.exclude(
            memberships__role='owner'
        )
        
        if orgs_without_owners.exists():
            self.log_issue(f'{orgs_without_owners.count()} organizations have no owners')
        
        # Check for duplicate slugs
        duplicate_slugs = PublishingOrganization.objects.values('slug').annotate(
            count=Count('slug')
        ).filter(count__gt=1)
        
        if duplicate_slugs.exists():
            self.log_issue(f'{duplicate_slugs.count()} organizations have duplicate slugs')
        
        # Check for missing required fields
        orgs_missing_data = PublishingOrganization.objects.filter(
            Q(summary='') | Q(description='')
        )
        
        if orgs_missing_data.exists():
            self.log_issue(
                f'{orgs_missing_data.count()} organizations missing summary or description',
                lambda: orgs_missing_data.update(
                    summary='Organization summary',
                    description='Organization description'
                )
            )
        
        self.stdout.write('   ✅ Organization validation complete')
    
    def validate_licenses(self):
        """Validate License data"""
        self.stdout.write('\n📜 Validating Licenses...')
        
        # Check for default license
        default_licenses = License.objects.filter(is_default=True)
        if default_licenses.count() == 0:
            self.log_issue(
                'No default license found',
                lambda: License.objects.filter(code='cc0').update(is_default=True)
            )
        elif default_licenses.count() > 1:
            self.log_issue(
                f'{default_licenses.count()} default licenses found (should be 1)',
                lambda: License.objects.filter(is_default=True).exclude(
                    id=default_licenses.first().id
                ).update(is_default=False)
            )
        
        # Check for licenses without terms
        licenses_without_terms = License.objects.filter(
            Q(license_terms__isnull=True) | Q(license_terms={})
        )
        
        if licenses_without_terms.exists():
            self.log_issue(f'{licenses_without_terms.count()} licenses missing terms')
        
        # Check for licenses without permissions
        licenses_without_permissions = License.objects.filter(
            Q(permissions__isnull=True) | Q(permissions={})
        )
        
        if licenses_without_permissions.exists():
            self.log_issue(f'{licenses_without_permissions.count()} licenses missing permissions')
        
        self.stdout.write('   ✅ License validation complete')
    
    def validate_resources(self):
        """Validate Resource and ResourceVersion data"""
        self.stdout.write('\n📚 Validating Resources...')
        
        # Check for resources without versions
        resources_without_versions = Resource.objects.annotate(
            version_count=Count('versions')
        ).filter(version_count=0)
        
        if resources_without_versions.exists():
            self.log_issue(f'{resources_without_versions.count()} resources have no versions')
        
        # Check for resources without latest version
        resources_without_latest = Resource.objects.exclude(
            versions__is_latest=True
        )
        
        if resources_without_latest.exists():
            self.log_issue(f'{resources_without_latest.count()} resources have no latest version')
        
        # Check for multiple latest versions
        resources_multiple_latest = Resource.objects.annotate(
            latest_count=Count('versions', filter=Q(versions__is_latest=True))
        ).filter(latest_count__gt=1)
        
        if resources_multiple_latest.exists():
            self.log_issue(f'{resources_multiple_latest.count()} resources have multiple latest versions')
        
        # Check for invalid semvar formats
        invalid_semvar = ResourceVersion.objects.exclude(
            semvar__regex=r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$'
        )
        
        if invalid_semvar.exists():
            self.log_issue(f'{invalid_semvar.count()} resource versions have invalid semvar format')
        
        # Check for missing storage URLs
        versions_no_storage = ResourceVersion.objects.filter(storage_url='')
        
        if versions_no_storage.exists():
            self.log_issue(f'{versions_no_storage.count()} resource versions missing storage URLs')
        
        self.stdout.write('   ✅ Resource validation complete')
    
    def validate_assets(self):
        """Validate Asset and AssetVersion data"""
        self.stdout.write('\n🎯 Validating Assets...')
        
        # Check for assets without versions
        assets_without_versions = Asset.objects.annotate(
            version_count=Count('versions')
        ).filter(version_count=0)
        
        if assets_without_versions.exists():
            self.log_issue(f'{assets_without_versions.count()} assets have no versions')
        
        # Check for assets with invalid categories
        valid_categories = ['mushaf', 'tafsir', 'recitation']
        invalid_category_assets = Asset.objects.exclude(category__in=valid_categories)
        
        if invalid_category_assets.exists():
            self.log_issue(f'{invalid_category_assets.count()} assets have invalid categories')
        
        # Check for assets without file sizes
        assets_no_size = Asset.objects.filter(Q(file_size='') | Q(file_size__isnull=True))
        
        if assets_no_size.exists():
            self.log_issue(f'{assets_no_size.count()} assets missing file size information')
        
        # Check for asset versions without file URLs
        versions_no_url = AssetVersion.objects.filter(file_url='')
        
        if versions_no_url.exists():
            self.log_issue(f'{versions_no_url.count()} asset versions missing file URLs')
        
        # Check for orphaned asset versions (resource version deleted)
        orphaned_versions = AssetVersion.objects.filter(resource_version__isnull=True)
        
        if orphaned_versions.exists():
            self.log_issue(
                f'{orphaned_versions.count()} orphaned asset versions found',
                lambda: orphaned_versions.delete()
            )
        
        self.stdout.write('   ✅ Asset validation complete')
    
    def validate_access_control(self):
        """Validate access control data integrity"""
        self.stdout.write('\n🔐 Validating Access Control...')
        
        # Check for access requests without corresponding users/assets
        invalid_requests = AssetAccessRequest.objects.filter(
            Q(developer_user__isnull=True) | Q(asset__isnull=True)
        )
        
        if invalid_requests.exists():
            self.log_issue(
                f'{invalid_requests.count()} invalid access requests found',
                lambda: invalid_requests.delete()
            )
        
        # Check for approved requests without access grants
        approved_no_access = AssetAccessRequest.objects.filter(
            status='approved',
            access_grant__isnull=True
        )
        
        if approved_no_access.exists():
            self.log_issue(f'{approved_no_access.count()} approved requests missing access grants')
        
        # Check for access grants without requests
        access_no_request = AssetAccess.all_objects.filter(asset_access_request__isnull=True)
        
        if access_no_request.exists():
            self.log_issue(f'{access_no_request.count()} access grants without requests')
        
        # Check for expired access that should be cleaned up
        from django.utils import timezone
        expired_access = AssetAccess.all_objects.filter(
            expires_at__lt=timezone.now()
        )
        
        if expired_access.exists() and self.detailed:
            self.stdout.write(f'   ℹ️  {expired_access.count()} expired access grants (consider cleanup)')
        
        # Check for duplicate access requests
        duplicate_requests = AssetAccessRequest.objects.values(
            'developer_user', 'asset'
        ).annotate(count=Count('id')).filter(count__gt=1)
        
        if duplicate_requests.exists():
            self.log_issue(f'{duplicate_requests.count()} duplicate access requests found')
        
        self.stdout.write('   ✅ Access control validation complete')
    
    def validate_usage_events(self):
        """Validate usage event data"""
        self.stdout.write('\n📊 Validating Usage Events...')
        
        # Check for events without users
        events_no_user = UsageEvent.objects.filter(developer_user__isnull=True)
        
        if events_no_user.exists():
            self.log_issue(
                f'{events_no_user.count()} usage events without users',
                lambda: events_no_user.delete()
            )
        
        # Check for asset events without valid asset references
        asset_events_invalid = UsageEvent.objects.filter(
            subject_kind='asset',
            asset_id__isnull=True
        )
        
        if asset_events_invalid.exists():
            self.log_issue(f'{asset_events_invalid.count()} asset events with invalid asset references')
        
        # Check for resource events without valid resource references
        resource_events_invalid = UsageEvent.objects.filter(
            subject_kind='resource',
            resource_id__isnull=True
        )
        
        if resource_events_invalid.exists():
            self.log_issue(f'{resource_events_invalid.count()} resource events with invalid resource references')
        
        # Check for events with both asset_id and resource_id
        conflicting_events = UsageEvent.objects.filter(
            asset_id__isnull=False,
            resource_id__isnull=False
        )
        
        if conflicting_events.exists():
            self.log_issue(f'{conflicting_events.count()} events reference both asset and resource')
        
        # Check for invalid usage kinds
        valid_usage_kinds = ['view', 'file_download', 'api_access']
        invalid_usage_events = UsageEvent.objects.exclude(usage_kind__in=valid_usage_kinds)
        
        if invalid_usage_events.exists():
            self.log_issue(f'{invalid_usage_events.count()} events with invalid usage kinds')
        
        self.stdout.write('   ✅ Usage event validation complete')
    
    def validate_distributions(self):
        """Validate distribution channel data"""
        self.stdout.write('\n📡 Validating Distributions...')
        
        # Check for distributions without resources
        distributions_no_resource = Distribution.objects.filter(resource__isnull=True)
        
        if distributions_no_resource.exists():
            self.log_issue(
                f'{distributions_no_resource.count()} distributions without resources',
                lambda: distributions_no_resource.delete()
            )
        
        # Check for distributions without endpoint URLs
        distributions_no_url = Distribution.objects.filter(
            Q(endpoint_url='') | Q(endpoint_url__isnull=True)
        )
        
        if distributions_no_url.exists():
            self.log_issue(f'{distributions_no_url.count()} distributions missing endpoint URLs')
        
        # Check for invalid format types
        valid_formats = ['rest_api', 'graphql', 'direct_download', 'streaming']
        invalid_format_distributions = Distribution.objects.exclude(
            format_type__in=valid_formats
        )
        
        if invalid_format_distributions.exists():
            self.log_issue(f'{invalid_format_distributions.count()} distributions with invalid format types')
        
        self.stdout.write('   ✅ Distribution validation complete')
    
    def validate_relationships(self):
        """Validate complex ERD relationships"""
        self.stdout.write('\n🔗 Validating Complex Relationships...')
        
        # Validate organization membership integrity
        invalid_memberships = PublishingOrganizationMember.objects.filter(
            Q(user__isnull=True) | Q(publishing_organization__isnull=True)
        )
        
        if invalid_memberships.exists():
            self.log_issue(
                f'{invalid_memberships.count()} invalid organization memberships',
                lambda: invalid_memberships.delete()
            )
        
        # Validate asset-resource-organization consistency
        inconsistent_assets = Asset.objects.exclude(
            versions__resource_version__resource__publishing_organization=F('publishing_organization')
        ).distinct()
        
        if inconsistent_assets.exists():
            self.log_issue(f'{inconsistent_assets.count()} assets with inconsistent organization relationships')
        
        # Validate license consistency between resources and assets
        inconsistent_licenses = Asset.objects.exclude(
            license=F('versions__resource_version__resource__default_license')
        ).distinct()
        
        if inconsistent_licenses.exists() and self.detailed:
            self.stdout.write(f'   ℹ️  {inconsistent_licenses.count()} assets with different license than resource default')
        
        # Validate access request workflow integrity
        broken_workflow = AssetAccess.all_objects.exclude(
            asset_access_request__asset=F('asset')
        ).exclude(
            asset_access_request__developer_user=F('user')
        )
        
        if broken_workflow.exists():
            self.log_issue(f'{broken_workflow.count()} access grants with broken workflow relationships')
        
        self.stdout.write('   ✅ Relationship validation complete')
    
    def get_summary_statistics(self):
        """Get summary statistics for data health"""
        stats = {
            'users': User.objects.count(),
            'organizations': PublishingOrganization.objects.count(),
            'organization_members': PublishingOrganizationMember.objects.count(),
            'licenses': License.objects.count(),
            'resources': Resource.objects.count(),
            'resource_versions': ResourceVersion.objects.count(),
            'assets': Asset.objects.count(),
            'asset_versions': AssetVersion.objects.count(),
            'access_requests': AssetAccessRequest.objects.count(),
            'access_grants': AssetAccess.all_objects.count(),
            'usage_events': UsageEvent.objects.count(),
            'distributions': Distribution.objects.count(),
        }
        
        if self.detailed:
            self.stdout.write('\n📈 Data Summary Statistics:')
            for key, value in stats.items():
                self.stdout.write(f'   {key.replace("_", " ").title()}: {value:,}')
        
        return stats
