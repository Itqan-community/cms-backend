"""
Django admin configuration for Analytics app
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from .models import LegacyUsageEvent


@admin.register(LegacyUsageEvent)
class UsageEventAdmin(admin.ModelAdmin):
    """Admin configuration for UsageEvent model"""
    list_display = [
        'user_email', 'resource_title', 'event_type', 
        'endpoint_short', 'bandwidth_total', 'occurred_at', 'is_successful_event'
    ]
    list_filter = [
        'event_type', 'occurred_at', 
        'distribution__format_type'
    ]
    search_fields = [
        'user__email', 'resource__title', 'endpoint', 
        'ip_address', 'user_agent'
    ]
    readonly_fields = [
        'id', 'user', 'resource', 'distribution', 'event_type',
        'endpoint', 'request_size', 'response_size', 'ip_address',
        'user_agent', 'metadata', 'occurred_at', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'occurred_at'
    ordering = ['-occurred_at']
    
    # Make the admin read-only since this is analytics data
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    fieldsets = (
        ('Event Information', {
            'fields': ('user', 'resource', 'distribution', 'event_type', 'occurred_at')
        }),
        ('Request Details', {
            'fields': ('endpoint', 'request_size', 'response_size')
        }),
        ('Client Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Additional Data', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('System Info', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        """Display user email"""
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def resource_title(self, obj):
        """Display resource title"""
        return obj.resource.title[:50] + ('...' if len(obj.resource.title) > 50 else '')
    resource_title.short_description = 'Resource'
    resource_title.admin_order_field = 'resource__title'
    
    def endpoint_short(self, obj):
        """Display shortened endpoint"""
        return obj.endpoint[:40] + ('...' if len(obj.endpoint) > 40 else '')
    endpoint_short.short_description = 'Endpoint'
    
    def bandwidth_total(self, obj):
        """Display total bandwidth used"""
        total_bytes = obj.get_bandwidth_total()
        if total_bytes > 1024 * 1024:  # MB
            return f"{total_bytes / (1024 * 1024):.1f} MB"
        elif total_bytes > 1024:  # KB
            return f"{total_bytes / 1024:.1f} KB"
        else:
            return f"{total_bytes} B"
    bandwidth_total.short_description = 'Bandwidth'
    
    def is_successful_event(self, obj):
        """Display if event was successful"""
        if obj.is_successful():
            return format_html(
                '<span style="color: green;">✓</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗</span>'
            )
    is_successful_event.short_description = 'Success'
    
    def changelist_view(self, request, extra_context=None):
        """Add analytics summary to changelist"""
        # Get summary statistics for the last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Get summary stats
        summary_stats = UsageEvent.objects.filter(
            occurred_at__gte=thirty_days_ago
        ).aggregate(
            total_events=Count('id'),
            total_users=Count('user', distinct=True),
            total_resources=Count('resource', distinct=True),
            total_bandwidth=Sum('request_size') + Sum('response_size'),
        )
        
        # Get event type breakdown
        event_breakdown = UsageEvent.objects.filter(
            occurred_at__gte=thirty_days_ago
        ).values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        extra_context = extra_context or {}
        extra_context.update({
            'summary_stats': summary_stats,
            'event_breakdown': event_breakdown,
            'summary_period': '30 days',
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related(
            'user', 'resource', 'distribution', 'user__role'
        )


# Custom admin site configuration
admin.site.site_header = "Itqan CMS Administration"
admin.site.site_title = "Itqan CMS Admin"
admin.site.index_title = "Welcome to Itqan CMS Administration"