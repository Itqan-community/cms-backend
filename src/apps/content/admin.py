"""
Django admin configuration for ERD-aligned Content models
Enhanced admin interface for comprehensive content management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from .models import (
    PublishingOrganization, PublishingOrganizationMember, License, Resource, 
    ResourceVersion, Asset, AssetVersion, AssetAccessRequest, AssetAccess, 
    UsageEvent, Distribution
)


# ============================================================================
# INLINE ADMINS
# ============================================================================

class PublishingOrganizationMemberInline(admin.TabularInline):
    """Inline admin for organization members"""
    model = PublishingOrganizationMember
    extra = 1
    fields = ['user', 'role']
    autocomplete_fields = ['user']


class ResourceVersionInline(admin.TabularInline):
    """Inline admin for resource versions"""
    model = ResourceVersion
    extra = 0
    fields = ['semvar', 'type', 'is_latest', 'size_bytes', 'storage_url']
    readonly_fields = ['created_at']


class AssetVersionInline(admin.TabularInline):
    """Inline admin for asset versions"""
    model = AssetVersion
    extra = 0
    fields = ['resource_version', 'name', 'size_bytes', 'file_url']
    readonly_fields = ['created_at']


class DistributionInline(admin.TabularInline):
    """Inline admin for resource distributions"""
    model = Distribution
    extra = 0
    fields = ['format_type', 'version', 'endpoint_url']


# ============================================================================
# MAIN MODEL ADMINS
# ============================================================================

@admin.register(PublishingOrganization)
class PublishingOrganizationAdmin(admin.ModelAdmin):
    """Enhanced admin for Publishing Organizations"""
    list_display = ['name', 'slug', 'member_count', 'resource_count', 'asset_count', 'total_downloads', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'slug', 'summary', 'bio']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [PublishingOrganizationMemberInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'icone_image_url', 'cover_url')
        }),
        ('Content', {
            'fields': ('summary', 'description', 'bio')
        }),
        ('Additional Information', {
            'fields': ('contact_email', 'website', 'location', 'social_links'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'Automatically managed timestamps'
        })
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        return super().get_queryset(request).annotate(
            member_count=Count('members'),
            resource_count=Count('resources'),
            asset_count=Count('assets', distinct=True),
            total_downloads=Sum('assets__download_count')
        )
    
    def member_count(self, obj):
        return obj.member_count
    member_count.short_description = 'Members'
    member_count.admin_order_field = 'member_count'
    
    def resource_count(self, obj):
        return obj.resource_count
    resource_count.short_description = 'Resources'
    resource_count.admin_order_field = 'resource_count'
    
    def asset_count(self, obj):
        return obj.asset_count or 0
    asset_count.short_description = 'Assets'
    asset_count.admin_order_field = 'asset_count'
    
    def total_downloads(self, obj):
        return obj.total_downloads or 0
    total_downloads.short_description = 'Total Downloads'
    total_downloads.admin_order_field = 'total_downloads'
    
    def view_resources(self, obj):
        """Link to view organization's resources"""
        url = reverse('admin:content_resource_changelist')
        return format_html(
            '<a href="{}?publishing_organization__id__exact={}">View Resources ({})</a>',
            url, obj.pk, obj.resource_count
        )
    view_resources.short_description = 'Resources'
    
    def view_assets(self, obj):
        """Link to view organization's assets"""
        url = reverse('admin:content_asset_changelist')
        return format_html(
            '<a href="{}?publishing_organization__id__exact={}">View Assets ({})</a>',
            url, obj.pk, obj.asset_count or 0
        )
    view_assets.short_description = 'Assets'


@admin.register(PublishingOrganizationMember)
class PublishingOrganizationMemberAdmin(admin.ModelAdmin):
    """Admin for Organization Members"""
    list_display = ['user', 'publishing_organization', 'role', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['user__email', 'publishing_organization__name']


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    """Admin for Licenses"""
    list_display = ['name', 'code', 'is_default', 'usage_count', 'created_at']
    list_filter = ['is_default', 'created_at']
    search_fields = ['name', 'code', 'summary']
    
    def usage_count(self, obj):
        return obj.assets.count() + obj.default_for_resources.count()
    usage_count.short_description = 'Usage Count'


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    """Enhanced admin for Resources"""
    list_display = ['name', 'publishing_organization', 'category', 'status', 'default_license', 'version_count', 'latest_version', 'created_at']
    list_filter = ['category', 'status', 'publishing_organization', 'default_license', 'created_at']
    search_fields = ['name', 'description', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ResourceVersionInline, DistributionInline]
    autocomplete_fields = ['publishing_organization', 'default_license']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'publishing_organization')
        }),
        ('Content', {
            'fields': ('description', 'category', 'status')
        }),
        ('Licensing', {
            'fields': ('default_license',)
        }),
        ('Multilingual Fields', {
            'fields': ('name_en', 'name_ar', 'description_en', 'description_ar'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        return super().get_queryset(request).select_related(
            'publishing_organization', 'default_license'
        ).annotate(
            annotated_version_count=Count('versions')
        )
    
    def version_count(self, obj):
        # Prefer annotated value; fall back to model property
        return getattr(obj, 'annotated_version_count', obj.version_count)
    version_count.short_description = 'Versions'
    version_count.admin_order_field = 'annotated_version_count'
    
    def latest_version(self, obj):
        latest = obj.get_latest_version()
        if latest:
            return f"{latest.semvar} ({latest.type})"
        return "No versions"
    latest_version.short_description = 'Latest Version'
    
    def view_versions(self, obj):
        """Link to view resource versions"""
        url = reverse('admin:content_resourceversion_changelist')
        count = getattr(obj, 'annotated_version_count', obj.version_count)
        return format_html(
            '<a href="{}?resource__id__exact={}">View Versions ({})</a>',
            url, obj.pk, count
        )
    view_versions.short_description = 'Versions'


@admin.register(ResourceVersion)
class ResourceVersionAdmin(admin.ModelAdmin):
    """Admin for Resource Versions"""
    list_display = ['resource', 'semvar', 'type', 'is_latest', 'size_bytes', 'created_at']
    list_filter = ['type', 'is_latest', 'created_at']
    search_fields = ['resource__name', 'semvar']


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    """Enhanced admin for Assets"""
    list_display = ['title', 'publishing_organization', 'category', 'license', 'download_count', 'view_count', 'access_requests_count', 'created_at']
    list_filter = ['category', 'license', 'publishing_organization', 'format', 'created_at']
    search_fields = ['title', 'name', 'description', 'long_description']
    inlines = [AssetVersionInline]
    autocomplete_fields = ['publishing_organization', 'license']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'name', 'publishing_organization', 'category')
        }),
        ('Content', {
            'fields': ('description', 'long_description', 'thumbnail_url')
        }),
        ('Technical Details', {
            'fields': ('format', 'encoding', 'file_size', 'version', 'language')
        }),
        ('Licensing', {
            'fields': ('license',)
        }),
        ('Statistics', {
            'fields': ('download_count', 'view_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    readonly_fields = ['created_at', 'updated_at', 'download_count', 'view_count']
    
    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        return super().get_queryset(request).select_related(
            'publishing_organization', 'license'
        ).annotate(
            access_requests_count=Count('access_requests'),
            user_accesses_count=Count('user_accesses')
        )
    
    def access_requests_count(self, obj):
        return obj.access_requests_count
    access_requests_count.short_description = 'Access Requests'
    access_requests_count.admin_order_field = 'access_requests_count'
    
    def user_accesses_count(self, obj):
        return obj.user_accesses_count
    user_accesses_count.short_description = 'Active Access'
    user_accesses_count.admin_order_field = 'user_accesses_count'
    
    def view_access_requests(self, obj):
        """Link to view asset access requests"""
        url = reverse('admin:content_assetaccessrequest_changelist')
        return format_html(
            '<a href="{}?asset__id__exact={}">View Requests ({})</a>',
            url, obj.pk, obj.access_requests_count
        )
    view_access_requests.short_description = 'Access Requests'
    
    def view_usage_events(self, obj):
        """Link to view usage events for this asset"""
        url = reverse('admin:content_usageevent_changelist')
        return format_html(
            '<a href="{}?asset_id__exact={}">View Usage Events</a>',
            url, obj.pk
        )
    view_usage_events.short_description = 'Usage Analytics'
    
    def file_size_display(self, obj):
        """Display file size in human readable format"""
        return obj.file_size
    file_size_display.short_description = 'File Size'
    
    def download_url_display(self, obj):
        """Display download URL with link"""
        latest_version = obj.get_latest_version()
        if latest_version and latest_version.file_url:
            return format_html(
                '<a href="{}" target="_blank">Download</a>',
                latest_version.file_url.url
            )
        return "No download URL"
    download_url_display.short_description = 'Download'


@admin.register(AssetVersion)
class AssetVersionAdmin(admin.ModelAdmin):
    """Admin for Asset Versions"""
    list_display = ['asset', 'resource_version', 'name', 'size_bytes', 'created_at']
    list_filter = ['created_at']
    search_fields = ['asset__title', 'name']


@admin.register(AssetAccessRequest)
class AssetAccessRequestAdmin(admin.ModelAdmin):
    """Enhanced admin for Asset Access Requests"""
    list_display = ['developer_user', 'asset', 'status', 'intended_use', 'created_at', 'approved_at', 'approved_by']
    list_filter = ['status', 'intended_use', 'created_at', 'approved_at']
    search_fields = ['developer_user__email', 'asset__title', 'developer_access_reason']
    readonly_fields = ['created_at', 'approved_at']
    autocomplete_fields = ['developer_user', 'asset', 'approved_by']
    
    fieldsets = (
        ('Request Information', {
            'fields': ('developer_user', 'asset', 'developer_access_reason', 'intended_use')
        }),
        ('Admin Review', {
            'fields': ('status', 'admin_response', 'approved_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'approved_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        """Bulk approve access requests"""
        count = 0
        for access_request in queryset.filter(status='pending'):
            try:
                access_request.approve_request(approved_by_user=request.user, auto_approved=False)
                count += 1
            except Exception as e:
                self.message_user(request, f"Error approving request {access_request.id}: {e}", level='ERROR')
        
        self.message_user(request, f"Successfully approved {count} requests.")
    approve_requests.short_description = "Approve selected requests"
    
    def reject_requests(self, request, queryset):
        """Bulk reject access requests"""
        count = 0
        for access_request in queryset.filter(status='pending'):
            try:
                access_request.reject_request(rejected_by_user=request.user, reason="Bulk rejection from admin")
                count += 1
            except Exception as e:
                self.message_user(request, f"Error rejecting request {access_request.id}: {e}", level='ERROR')
        
        self.message_user(request, f"Successfully rejected {count} requests.")
    reject_requests.short_description = "Reject selected requests"
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'developer_user', 'asset', 'approved_by'
        )


@admin.register(AssetAccess)
class AssetAccessAdmin(admin.ModelAdmin):
    """Enhanced admin for Asset Access"""
    list_display = ['user', 'asset', 'effective_license', 'granted_at', 'expires_at', 'is_active_status', 'usage_count']
    list_filter = ['granted_at', 'expires_at', 'effective_license']
    search_fields = ['user__email', 'asset__title']
    readonly_fields = ['granted_at', 'usage_count']
    autocomplete_fields = ['user', 'asset', 'effective_license']
    
    fieldsets = (
        ('Access Information', {
            'fields': ('asset_access_request', 'user', 'asset')
        }),
        ('License Information', {
            'fields': ('effective_license',)
        }),
        ('Access Details', {
            'fields': ('granted_at', 'expires_at', 'download_url')
        }),
        ('Statistics', {
            'fields': ('usage_count',),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'user', 'asset', 'effective_license', 'asset_access_request'
        )
    
    def is_active_status(self, obj):
        """Show if access is currently active"""
        return "✅ Active" if obj.is_active else "❌ Expired"
    is_active_status.short_description = 'Status'
    
    def usage_count(self, obj):
        """Count usage events for this access"""
        from django.db.models import Q
        return UsageEvent.objects.filter(
            developer_user=obj.user,
            asset_id=obj.asset.id
        ).count()
    usage_count.short_description = 'Usage Events'


@admin.register(UsageEvent)
class UsageEventAdmin(admin.ModelAdmin):
    """Admin for Usage Events"""
    list_display = ['developer_user', 'usage_kind', 'subject_kind', 'created_at']
    list_filter = ['usage_kind', 'subject_kind', 'created_at']
    search_fields = ['developer_user__email']
    readonly_fields = ['created_at']


@admin.register(Distribution)
class DistributionAdmin(admin.ModelAdmin):
    """Admin for Distributions"""
    list_display = ['resource', 'format_type', 'version', 'created_at']
    list_filter = ['format_type', 'created_at']
    search_fields = ['resource__name', 'endpoint_url']