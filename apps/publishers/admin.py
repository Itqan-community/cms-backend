from django.contrib import admin
from django.db.models import Count
from django.db.models import Sum
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Publisher, PublisherMember,
)


class PublisherMemberInline(admin.TabularInline):
    model = PublisherMember
    extra = 0
    fields = ["user", "role"]
    autocomplete_fields = ["user"]
    raw_id_fields = ["user"]
@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "icon_url", "member_count", "resource_count", "asset_count", "created_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [PublisherMemberInline]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "slug", "icon_url"),
            },
        ),
        (
            "Content",
            {
                "fields": ("description",),
            },
        ),
        (
            "Additional Information",
            {
                "fields": ("contact_email", "website", "address"),
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
                asset_count=Count("resources__assets", distinct=True)
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

    @admin.display(description="Resources")
    def view_resources(self, obj):
        """Link to view publisher's resources"""
        url = reverse("admin:content_resource_changelist")
        return format_html(
            '<a href="{}?publisher__id__exact={}">View Resources ({})</a>',
            url,
            obj.pk,
            obj.resource_count,
        )

    @admin.display(description="Assets")
    def view_assets(self, obj):
        """Link to view publisher's assets"""
        url = reverse("admin:content_asset_changelist")
        return format_html(
            '<a href="{}?publisher__id__exact={}">View Assets ({})</a>',
            url,
            obj.pk,
            obj.asset_count or 0,
        )


@admin.register(PublisherMember)
class PublisherMemberAdmin(admin.ModelAdmin):
    list_display = ["user", "publisher", "role", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["user__email", "publisher__name"]

