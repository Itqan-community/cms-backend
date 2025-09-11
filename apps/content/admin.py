from django.contrib import admin
from django.db.models import Count
from django.db.models import Sum
from django.urls import reverse
from django.utils.html import format_html

from .models import Asset
from .models import AssetVersion
from .models import License
from .models import Publisher
from .models import PublisherMember
from .models import Resource
from .models import ResourceVersion


class PublisherMemberInline(admin.TabularInline):
    model = PublisherMember
    extra = 0
    fields = ["user", "role"]
    autocomplete_fields = ["user"]
    raw_id_fields = ["user"]


class ResourceVersionInline(admin.TabularInline):
    model = ResourceVersion
    extra = 0
    fields = ["semvar", "type", "is_latest", "storage_url"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["resource"]


class AssetVersionInline(admin.TabularInline):
    model = AssetVersion
    extra = 0
    fields = ["resource_version", "name", "human_readable_size", "file_url"]
    readonly_fields = ["created_at"]


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "member_count", "resource_count", "asset_count", "total_downloads", "created_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["name", "slug", "summary"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [PublisherMemberInline]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "slug"),
            },
        ),
        (
            "Content",
            {
                "fields": ("summary", "description"),
            },
        ),
        (
            "Additional Information",
            {
                "fields": ("contact_email", "website", "location", "social_links"),
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
                "description": "Automatically managed timestamps",
            },
        ),
    )
    readonly_fields = ["created_at", "updated_at"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                member_count=Count("members"),
                resource_count=Count("resources"),
                asset_count=Count("resources__assets", distinct=True),
                total_downloads=Sum("resources__assets__download_count"),
            )
        )

    @admin.display(description="Members", ordering="member_count")
    def member_count(self, obj):
        return obj.member_count

    @admin.display(description="Resources", ordering="resource_count")
    def resource_count(self, obj):
        return obj.resource_count

    @admin.display(description="Assets", ordering="asset_count")
    def asset_count(self, obj):
        return obj.asset_count or 0

    @admin.display(description="Total Downloads", ordering="total_downloads")
    def total_downloads(self, obj):
        return obj.total_downloads or 0

    @admin.display(description="Resources")
    def view_resources(self, obj):
        """Link to view organization's resources"""
        url = reverse("admin:content_resource_changelist")
        return format_html(
            '<a href="{}?publishing_organization__id__exact={}">View Resources ({})</a>',
            url,
            obj.pk,
            obj.resource_count,
        )

    @admin.display(description="Assets")
    def view_assets(self, obj):
        """Link to view organization's assets"""
        url = reverse("admin:content_asset_changelist")
        return format_html(
            '<a href="{}?publishing_organization__id__exact={}">View Assets ({})</a>',
            url,
            obj.pk,
            obj.asset_count or 0,
        )


@admin.register(PublisherMember)
class PublishingOrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ["user", "publisher", "role", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["user__email", "publisher__name"]


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "short_name", "is_default"]
    list_filter = ["is_default"]
    search_fields = ["name", "code", "short_name"]


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    """Enhanced admin for Resources"""

    list_display = [
        "name",
        "publisher",
        "category",
        "status",
        "default_license",
        "version_count",
        "latest_version",
        "created_at",
    ]
    list_filter = ["category", "status", "publisher", "default_license", "created_at"]
    search_fields = ["name", "description", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ResourceVersionInline]
    autocomplete_fields = ["publisher", "default_license"]

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
            "Licensing",
            {
                "fields": ("default_license",),
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
            .select_related(
                "publisher",
                "default_license",
            )
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
            return f"{latest.semvar} ({latest.type})"
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
    """Admin for Resource Versions"""

    list_display = ["resource", "semvar", "file_type", "is_latest", "size_bytes", "created_at"]
    list_filter = ["file_type", "is_latest", "created_at"]
    search_fields = ["resource__name", "semvar"]


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    """Enhanced admin for Assets"""

    list_display = [
        "title",
        "get_publisher",
        "category",
        "license",
        "access_requests_count",
        "created_at",
    ]
    list_filter = ["category", "license", "resource__publisher", "format", "created_at"]
    search_fields = ["title", "name", "description", "long_description"]
    inlines = [AssetVersionInline]
    autocomplete_fields = ["resource", "license"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("title", "name", "resource", "category"),
            },
        ),
        (
            "Content",
            {
                "fields": ("description", "long_description", "thumbnail_url"),
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
                "resource__publisher",
                "license",
            )
            .annotate(
                access_requests_count=Count("access_requests"),
                user_accesses_count=Count("user_accesses"),
            )
        )

    @admin.display(description="Publisher", ordering="resource__publisher")
    def get_publisher(self, obj):
        """Display publishing organization through resource"""
        return obj.resource.publisher if obj.resource else None

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
    """Admin for Asset Versions"""

    list_display = ["asset", "resource_version", "name", "size_bytes", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["asset__title", "name"]
