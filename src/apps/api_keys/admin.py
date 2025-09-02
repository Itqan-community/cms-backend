"""
Django admin configuration for API key management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import APIKey, APIKeyUsage, RateLimitEvent


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """
    Admin interface for API keys
    """
    list_display = [
        'name', 'user', 'key_prefix_display', 'status_display',
        'rate_limit', 'total_requests', 'last_used_at', 'created_at'
    ]
    list_filter = [
        'is_active', 'user__role__name', 'created_at', 'expires_at',
        'revoked_at'
    ]
    search_fields = ['name', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = [
        'id', 'key_prefix', 'key_hash', 'total_requests', 'last_used_at',
        'last_used_ip', 'revoked_at', 'revoked_by', 'created_at', 'updated_at'
    ]
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'id', 'name', 'user', 'description'
            )
        }),
        ('Key Details', {
            'fields': (
                'key_prefix', 'key_hash'
            )
        }),
        ('Permissions & Limits', {
            'fields': (
                'permissions', 'allowed_ips', 'rate_limit'
            )
        }),
        ('Usage Statistics', {
            'fields': (
                'total_requests', 'last_used_at', 'last_used_ip'
            )
        }),
        ('Lifecycle', {
            'fields': (
                'expires_at', 'revoked_at', 'revoked_by', 'revoked_reason',
                'is_active', 'created_at', 'updated_at'
            )
        }),
    )
    
    def key_prefix_display(self, obj):
        """Display masked key prefix"""
        return f"{obj.key_prefix}***"
    key_prefix_display.short_description = 'Key Preview'
    
    def status_display(self, obj):
        """Display colored status"""
        if obj.is_revoked():
            color = 'red'
            status = 'Revoked'
        elif obj.is_expired():
            color = 'orange'
            status = 'Expired'
        elif obj.is_valid():
            color = 'green'
            status = 'Active'
        else:
            color = 'gray'
            status = 'Inactive'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, status
        )
    status_display.short_description = 'Status'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user', 'revoked_by')
    
    actions = ['revoke_keys']
    
    def revoke_keys(self, request, queryset):
        """Batch action to revoke API keys"""
        count = 0
        for api_key in queryset:
            if not api_key.is_revoked():
                api_key.revoke(
                    revoked_by=request.user,
                    reason="Revoked via admin action"
                )
                count += 1
        
        self.message_user(
            request,
            f'Successfully revoked {count} API key(s).'
        )
    revoke_keys.short_description = "Revoke selected API keys"


@admin.register(APIKeyUsage)
class APIKeyUsageAdmin(admin.ModelAdmin):
    """
    Admin interface for API key usage logs
    """
    list_display = [
        'api_key_name', 'endpoint', 'method', 'status_code_display',
        'ip_address', 'response_time', 'created_at'
    ]
    list_filter = [
        'method', 'status_code', 'api_key__user__role__name', 'created_at'
    ]
    search_fields = [
        'api_key__name', 'endpoint', 'ip_address', 'user_agent'
    ]
    readonly_fields = [
        'api_key', 'endpoint', 'method', 'status_code', 'ip_address',
        'user_agent', 'request_data', 'response_time', 'created_at'
    ]
    date_hierarchy = 'created_at'
    
    def api_key_name(self, obj):
        """Display API key name with link"""
        url = reverse('admin:api_keys_apikey_change', args=[obj.api_key.id])
        return format_html('<a href="{}">{}</a>', url, obj.api_key.name)
    api_key_name.short_description = 'API Key'
    
    def status_code_display(self, obj):
        """Display colored status code"""
        if obj.status_code < 300:
            color = 'green'
        elif obj.status_code < 400:
            color = 'blue'
        elif obj.status_code < 500:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status_code
        )
    status_code_display.short_description = 'Status'
    
    def has_add_permission(self, request):
        """Disable adding usage logs manually"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing usage logs"""
        return False


@admin.register(RateLimitEvent)
class RateLimitEventAdmin(admin.ModelAdmin):
    """
    Admin interface for rate limit events
    """
    list_display = [
        'api_key_name', 'limit_type', 'endpoint', 'ip_address',
        'violation_details', 'created_at'
    ]
    list_filter = [
        'limit_type', 'created_at'
    ]
    search_fields = [
        'api_key__name', 'ip_address', 'endpoint'
    ]
    readonly_fields = [
        'api_key', 'ip_address', 'endpoint', 'method', 'limit_type',
        'current_count', 'limit_value', 'window_seconds', 'created_at'
    ]
    date_hierarchy = 'created_at'
    
    def api_key_name(self, obj):
        """Display API key name with link"""
        if obj.api_key:
            url = reverse('admin:api_keys_apikey_change', args=[obj.api_key.id])
            return format_html('<a href="{}">{}</a>', url, obj.api_key.name)
        return 'Anonymous'
    api_key_name.short_description = 'API Key'
    
    def violation_details(self, obj):
        """Display violation details"""
        return f"{obj.current_count}/{obj.limit_value} in {obj.window_seconds}s"
    violation_details.short_description = 'Violation'
    
    def has_add_permission(self, request):
        """Disable adding rate limit events manually"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing rate limit events"""
        return False


# Custom admin views for API key management
class APIKeyManagementAdmin(admin.ModelAdmin):
    """
    Custom admin view for API key management and monitoring
    """
    def has_module_permission(self, request):
        """Only show to admin users"""
        return request.user.is_admin() if hasattr(request.user, 'is_admin') else request.user.is_superuser


# Register a custom admin page for API statistics
try:
    from django.contrib.admin import AdminSite
    from django.urls import path
    from django.shortcuts import render
    from django.http import JsonResponse
    from django.db.models import Count
    from datetime import timedelta
    
    class APIStatsView:
        """
        Custom admin view for API statistics
        """
        @staticmethod
        def api_stats_view(request):
            """
            Display API statistics dashboard
            """
            if not request.user.is_admin():
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            
            # Calculate statistics
            total_keys = APIKey.objects.count()
            active_keys = APIKey.objects.filter(
                is_active=True,
                revoked_at__isnull=True
            ).count()
            
            # Recent activity (last 7 days)
            week_ago = timezone.now() - timedelta(days=7)
            recent_requests = APIKeyUsage.objects.filter(
                created_at__gte=week_ago
            ).count()
            
            recent_violations = RateLimitEvent.objects.filter(
                created_at__gte=week_ago
            ).count()
            
            # Top API keys by usage
            top_keys = APIKeyUsage.objects.filter(
                created_at__gte=week_ago
            ).values('api_key__name').annotate(
                requests=Count('id')
            ).order_by('-requests')[:10]
            
            context = {
                'title': 'API Key Statistics',
                'total_keys': total_keys,
                'active_keys': active_keys,
                'recent_requests': recent_requests,
                'recent_violations': recent_violations,
                'top_keys': top_keys,
            }
            
            return render(request, 'admin/api_keys/stats.html', context)
    
    # You would need to create the template at:
    # backend/apps/api_keys/templates/admin/api_keys/stats.html
    
except ImportError:
    # If Django admin is not available, skip custom views
    pass
