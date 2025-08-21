"""
Django admin configuration for Content app
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Resource, Distribution


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    """Admin configuration for Resource model"""
    list_display = [
        'title', 'resource_type', 'language', 'publisher', 
        'version', 'is_published', 'published_at', 'created_at'
    ]
    list_filter = [
        'resource_type', 'language', 'is_active', 
        'published_at', 'created_at', 'publisher'
    ]
    search_fields = ['title', 'description', 'checksum']
    readonly_fields = ['id', 'checksum', 'created_at', 'updated_at']
    date_hierarchy = 'published_at'
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'resource_type', 'language', 'version')
        }),
        ('Publisher Info', {
            'fields': ('publisher', 'published_at')
        }),
        ('Content Verification', {
            'fields': ('checksum',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('System Info', {
            'fields': ('id', 'is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_published(self, obj):
        """Display publication status"""
        if obj.published_at:
            return format_html(
                '<span style="color: green;">✓ Published</span>'
            )
        return format_html(
            '<span style="color: orange;">Draft</span>'
        )
    is_published.short_description = 'Status'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('publisher', 'publisher__role')


@admin.register(Distribution)
class DistributionAdmin(admin.ModelAdmin):
    """Admin configuration for Distribution model"""
    list_display = [
        'resource', 'format_type', 'version', 'endpoint_url', 
        'is_active', 'access_requests_count', 'created_at'
    ]
    list_filter = [
        'format_type', 'is_active', 'created_at', 'resource__resource_type'
    ]
    search_fields = ['resource__title', 'endpoint_url', 'version']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {
            'fields': ('resource', 'format_type', 'version', 'endpoint_url')
        }),
        ('Access Configuration', {
            'fields': ('access_config',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('System Info', {
            'fields': ('id', 'is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def access_requests_count(self, obj):
        """Display count of access requests for this distribution"""
        count = obj.access_requests.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:licensing_accessrequest_changelist')
            return format_html(
                '<a href="{}?distribution__id__exact={}">{} requests</a>',
                url, obj.id, count
            )
        return "0 requests"
    access_requests_count.short_description = 'Access Requests'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('resource', 'resource__publisher')