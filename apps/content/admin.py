
from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .models import Asset
from .models import AssetPreview
from .models import (
    AssetAccessRequest, AssetAccess,
    UsageEvent, Distribution
)
from .models import AssetVersion
from .models import Resource
from .models import ResourceVersion


class ResourceVersionInline(admin.TabularInline):
    model = ResourceVersion
    extra = 0
    fields = ["semvar", "file_type", "is_latest", "storage_url"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["resource"]


class AssetVersionInline(admin.TabularInline):
    model = AssetVersion
    extra = 0
    fields = ["resource_version", "name", "file_url"]
    readonly_fields = ["created_at"]


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "publisher",
        "category",
        "status",
        "latest_version",
        "created_at",
    ]
    list_filter = ["category", "status", "publisher", "created_at"]
    search_fields = ["name", "description", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ResourceVersionInline]
    raw_id_fields = ["publisher"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "slug", "publisher"),
            },
        ),
        (
            "Content",
            {
                "fields": ("description", "category", "status"),
            },
        ),
        (
            "Multilingual Fields",
            {
                "fields": ("name_en", "name_ar", "description_en", "description_ar"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        return (
            super()
            .get_queryset(request)
            .select_related("publisher")
            .annotate(
                annotated_version_count=Count("versions"),
            )
        )

    @admin.display(description="Versions", ordering="annotated_version_count")
    def version_count(self, obj):
        # Prefer annotated value; fall back to model property
        return getattr(obj, "annotated_version_count", obj.version_count)

    @admin.display(description="Latest Version")
    def latest_version(self, obj):
        latest = obj.get_latest_version()
        if latest:
            return f"{latest.semvar}"
        return "No versions"

    @admin.display(description="Versions")
    def view_versions(self, obj):
        """Link to view resource versions"""
        url = reverse("admin:content_resourceversion_changelist")
        count = getattr(obj, "annotated_version_count", obj.version_count)
        return format_html(
            '<a href="{}?resource__id__exact={}">View Versions ({})</a>',
            url,
            obj.pk,
            count,
        )


@admin.register(ResourceVersion)
class ResourceVersionAdmin(admin.ModelAdmin):
    list_display = ["resource", "semvar", "file_type", "is_latest", "size_bytes", "created_at"]
    list_filter = ["file_type", "is_latest", "created_at"]
    search_fields = ["resource__name", "semvar"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "publisher_name",
        "category",
        "file_size",
        "format",
        "license",
        "created_at",
    ]
    list_filter = ["category", "license", "resource__publisher", "format", "created_at"]
    search_fields = ["name", "description", "long_description"]
    inlines = [AssetVersionInline]
    raw_id_fields = ["resource"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "resource", "category"),
            },
        ),
        (
            "Content",
            {
                "fields": ("description", "long_description", "thumbnail_url"),
            },
        ),
        (
            "Multilingual Fields",
            {
                "fields": ("name_en", "name_ar", "description_en", "description_ar", "long_description_en", "long_description_ar"),
                "classes": ("collapse",),
            },
        ),
        (
            "Technical Details",
            {
                "fields": ("format", "encoding", "file_size", "version", "language"),
            },
        ),
        (
            "Licensing",
            {
                "fields": ("license",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        """Optimize queryset with annotations"""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "resource__publisher"
            )
            .annotate(
                access_requests_count=Count("access_requests"),
                user_accesses_count=Count("user_accesses"),
            )
        )

    @admin.display(description="Publisher", ordering="resource__publisher")
    def publisher_name(self, obj):
        return obj.resource.publisher.name

    @admin.display(description="Access Requests", ordering="access_requests_count")
    def access_requests_count(self, obj):
        return obj.access_requests_count

    @admin.display(description="Active Access", ordering="user_accesses_count")
    def user_accesses_count(self, obj):
        return obj.user_accesses_count

    @admin.display(description="Access Requests")
    def view_access_requests(self, obj):
        """Link to view asset access requests"""
        url = reverse("admin:content_assetaccessrequest_changelist")
        return format_html(
            '<a href="{}?asset__id__exact={}">View Requests ({})</a>',
            url,
            obj.pk,
            obj.access_requests_count,
        )

    @admin.display(description="Usage Analytics")
    def view_usage_events(self, obj):
        """Link to view usage events for this asset"""
        url = reverse("admin:content_usageevent_changelist")
        return format_html(
            '<a href="{}?asset_id__exact={}">View Usage Events</a>',
            url,
            obj.pk,
        )

    @admin.display(description="File Size")
    def file_size_display(self, obj):
        """Display file size in human-readable format"""
        return obj.file_size

    @admin.display(description="Download")
    def download_url_display(self, obj):
        """Display download URL with link"""
        latest_version = obj.get_latest_version()
        if latest_version and latest_version.file_url:
            return format_html(
                '<a href="{}" target="_blank">Download</a>',
                latest_version.file_url.url,
            )
        return "No download URL"


@admin.register(AssetVersion)
class AssetVersionAdmin(admin.ModelAdmin):
    list_display = ["asset", "resource_version", "name", "size_bytes", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["asset__name", "name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AssetPreview)
class AssetPreviewAdmin(admin.ModelAdmin):
    list_display = ["asset", "image_url", "title", "description", "order", "created_at"]
    search_fields = ["asset__name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AssetAccessRequest)
class AssetAccessRequestAdmin(admin.ModelAdmin):
    list_display = ['developer_user', 'asset', 'status', 'intended_use', 'created_at', 'approved_at', 'approved_by']
    list_filter = ['status', 'intended_use', 'created_at', 'approved_at']
    search_fields = ['developer_user__email', 'asset__name', 'developer_access_reason']
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
    list_display = ['user', 'asset', 'effective_license', 'granted_at', 'expires_at', 'is_active_status', 'usage_count']
    list_filter = ['granted_at', 'expires_at', 'effective_license']
    search_fields = ['user__email', 'asset__name']
    readonly_fields = ['granted_at', 'usage_count']
    raw_id_fields = ['user', 'asset']
    
    fieldsets = (
        ('Access Information', {
            'fields': ('asset_access_request', 'user', 'asset')
        }),
        ('License Information', {
            'fields': ('effective_license',)
        }),
        ('Access Details', {
            'fields': ('granted_at', 'expires_at', 'download_url'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('usage_count',),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'user', 'asset', 'asset_access_request'
        )
    
    def is_active_status(self, obj):
        """Show if access is currently active"""
        return "✅ Active" if obj.is_active else "❌ Expired"
    is_active_status.short_description = 'Status'

    def usage_count(self, obj):
        """Count usage events for this access"""
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
    readonly_fields = [
        'developer_user',
        'usage_kind',
        'subject_kind',
        'resource_id',
        'asset_id',
        'metadata',
        'ip_address',
        'user_agent',
        'created_at',
        'updated_at',
    ]

    # Make the model read-only in admin
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

