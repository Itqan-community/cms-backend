"""
Django admin configuration for ERD-aligned Content models
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PublishingOrganization, PublishingOrganizationMember, License, Resource, 
    ResourceVersion, Asset, AssetVersion, AssetAccessRequest, AssetAccess, 
    UsageEvent, Distribution
)


@admin.register(PublishingOrganization)
class PublishingOrganizationAdmin(admin.ModelAdmin):
    """Admin for Publishing Organizations"""
    list_display = ['name', 'slug', 'verified', 'member_count', 'created_at']
    list_filter = ['verified', 'created_at']
    search_fields = ['name', 'slug', 'summary']
    prepopulated_fields = {'slug': ('name',)}
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'


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
    """Admin for Resources"""
    list_display = ['name', 'publishing_organization', 'category', 'status', 'created_at']
    list_filter = ['category', 'status', 'publishing_organization', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ResourceVersion)
class ResourceVersionAdmin(admin.ModelAdmin):
    """Admin for Resource Versions"""
    list_display = ['resource', 'semvar', 'type', 'is_latest', 'size_bytes', 'created_at']
    list_filter = ['type', 'is_latest', 'created_at']
    search_fields = ['resource__name', 'semvar']


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    """Admin for Assets"""
    list_display = ['title', 'publishing_organization', 'category', 'license', 'download_count', 'created_at']
    list_filter = ['category', 'license', 'publishing_organization', 'created_at']
    search_fields = ['title', 'name', 'description']


@admin.register(AssetVersion)
class AssetVersionAdmin(admin.ModelAdmin):
    """Admin for Asset Versions"""
    list_display = ['asset', 'resource_version', 'name', 'size_bytes', 'created_at']
    list_filter = ['created_at']
    search_fields = ['asset__title', 'name']


@admin.register(AssetAccessRequest)
class AssetAccessRequestAdmin(admin.ModelAdmin):
    """Admin for Asset Access Requests"""
    list_display = ['developer_user', 'asset', 'status', 'intended_use', 'created_at', 'approved_at']
    list_filter = ['status', 'intended_use', 'created_at']
    search_fields = ['developer_user__email', 'asset__title']
    readonly_fields = ['created_at', 'approved_at']


@admin.register(AssetAccess)
class AssetAccessAdmin(admin.ModelAdmin):
    """Admin for Asset Access"""
    list_display = ['user', 'asset', 'granted_at', 'expires_at']
    list_filter = ['granted_at', 'expires_at']
    search_fields = ['user__email', 'asset__title']
    readonly_fields = ['granted_at']


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