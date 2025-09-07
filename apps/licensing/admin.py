"""
Django admin configuration for Licensing app
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import AccessRequest
from .models import LegacyLicense


@admin.register(LegacyLicense)
class LicenseAdmin(admin.ModelAdmin):
    """Admin configuration for License model"""

    list_display = [
        "resource",
        "license_type",
        "requires_approval",
        "is_effective_now",
        "effective_from",
        "expires_at",
        "created_at",
    ]
    list_filter = [
        "license_type",
        "requires_approval",
        "is_active",
        "effective_from",
        "expires_at",
        "created_at",
    ]
    search_fields = ["resource__title", "terms"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "effective_from"
    ordering = ["-created_at"]

    fieldsets = (
        (
            None,
            {
                "fields": ("resource", "license_type", "requires_approval"),
            },
        ),
        (
            "License Terms",
            {
                "fields": ("terms",),
            },
        ),
        (
            "Validity Period",
            {
                "fields": ("effective_from", "expires_at"),
            },
        ),
        (
            "Restrictions",
            {
                "fields": ("geographic_restrictions", "usage_restrictions"),
                "classes": ("collapse",),
            },
        ),
        (
            "System Info",
            {
                "fields": ("id", "is_active", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(
        description="Status",
    )
    def is_effective_now(self, obj):
        """Display if license is currently effective"""
        if obj.is_effective():
            return format_html(
                '<span style="color: green;">✓ Effective</span>',
            )
        if obj.is_expired():
            return format_html(
                '<span style="color: red;">✗ Expired</span>',
            )
        return format_html(
            '<span style="color: orange;">⏳ Future</span>',
        )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related("resource", "resource__publisher")


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    """Admin configuration for AccessRequest model"""

    list_display = [
        "requester",
        "distribution_resource",
        "distribution_format",
        "status",
        "requested_at",
        "reviewed_at",
        "approved_by",
    ]
    list_filter = [
        "status",
        "requested_at",
        "reviewed_at",
        "distribution__format_type",
    ]
    search_fields = [
        "requester__email",
        "requester__first_name",
        "requester__last_name",
        "distribution__resource__title",
        "justification",
    ]
    readonly_fields = ["id", "requested_at", "reviewed_at", "created_at", "updated_at"]
    date_hierarchy = "requested_at"
    ordering = ["-requested_at"]

    fieldsets = (
        (
            None,
            {
                "fields": ("requester", "distribution", "status"),
            },
        ),
        (
            "Request Details",
            {
                "fields": ("justification",),
            },
        ),
        (
            "Review Information",
            {
                "fields": ("admin_notes", "approved_by", "reviewed_at", "expires_at"),
            },
        ),
        (
            "System Info",
            {
                "fields": (
                    "id",
                    "is_active",
                    "requested_at",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["approve_requests", "reject_requests"]

    @admin.display(
        description="Resource",
    )
    def distribution_resource(self, obj):
        """Display resource title for the distribution"""
        return obj.distribution.resource.title

    @admin.display(
        description="Format",
    )
    def distribution_format(self, obj):
        """Display format type of the distribution"""
        return obj.distribution.get_format_type_display()

    @admin.action(
        description="Approve selected access requests",
    )
    def approve_requests(self, request, queryset):
        """Admin action to approve selected requests"""
        approved_count = 0
        for access_request in queryset.filter(status="pending"):
            access_request.approve(
                admin_user=request.user,
                admin_notes="Bulk approved by admin",
            )
            approved_count += 1

        self.message_user(
            request,
            f"Successfully approved {approved_count} access requests.",
        )

    @admin.action(
        description="Reject selected access requests",
    )
    def reject_requests(self, request, queryset):
        """Admin action to reject selected requests"""
        rejected_count = 0
        for access_request in queryset.filter(status="pending"):
            access_request.reject(
                admin_user=request.user,
                admin_notes="Bulk rejected by admin",
            )
            rejected_count += 1

        self.message_user(
            request,
            f"Successfully rejected {rejected_count} access requests.",
        )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return (
            super()
            .get_queryset(request)
            .select_related(
                "requester",
                "distribution",
                "distribution__resource",
                "distribution__resource__publisher",
                "approved_by",
            )
        )
