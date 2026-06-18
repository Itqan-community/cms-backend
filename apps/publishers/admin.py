from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .models import Domain, Publisher, PublisherMember, PublisherMemberInvitation


class PublisherMemberInline(admin.TabularInline):
    model = PublisherMember
    extra = 0
    fields = ["user", "role"]
    raw_id_fields = ["user"]


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "icon_url",
        "member_count",
        "asset_count",
        "created_at",
    ]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ("name_en",)}
    inlines = [PublisherMemberInline]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name_en", "name_ar", "slug", "icon_url"),
            },
        ),
        (
            "Content",
            {
                "fields": (
                    "description_en",
                    "description_ar",
                ),
            },
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "contact_email",
                    "website",
                    "address",
                    "country",
                    "foundation_year",
                    "is_verified",
                    "mixpanel_board_url",
                )
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
                asset_count=Count("assets", distinct=True),
            )
        )

    @admin.display(description="Members", ordering="member_count")
    def member_count(self, obj):
        return obj.member_count

    @admin.display(description="Assets", ordering="asset_count")
    def asset_count(self, obj):
        return obj.asset_count or 0

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
    raw_id_fields = ["user", "publisher"]


@admin.register(PublisherMemberInvitation)
class PublisherMemberInvitationAdmin(admin.ModelAdmin):
    list_display = [
        "email",
        "publisher",
        "role",
        "status",
        "invited_by",
        "expires_at",
        "accepted_at",
        "created_at",
    ]
    list_filter = ["status", "created_at", "expires_at"]
    search_fields = [
        "member__user__email",
        "publisher__name",
        "invited_by__email",
    ]
    raw_id_fields = ["publisher", "member", "invited_by", "cancelled_by"]
    readonly_fields = [
        "token_hash",
        "accepted_at",
        "cancelled_at",
        "created_at",
        "updated_at",
    ]

    @admin.display(description="Email")
    def email(self, obj):
        return obj.email

    @admin.display(description="Role")
    def role(self, obj):
        return obj.role


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ["domain", "publisher", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["domain", "publisher__name"]
    raw_id_fields = ["publisher"]
