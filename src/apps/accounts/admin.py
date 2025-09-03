"""
Django admin configuration for Accounts app
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin configuration for Role model"""
    list_display = ['name', 'description', 'is_active', 'user_count', 'created_at']
    list_filter = ['is_active', 'name', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Permissions', {
            'fields': ('permissions',),
            'classes': ('collapse',)
        }),
        ('System Info', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_count(self, obj):
        """Display count of users with this role"""
        return obj.users.filter(is_active=True).count()
    user_count.short_description = 'Active Users'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for User model"""
    list_display = [
        'email', 'get_full_name', 'role', 'auth_provider', 'email_verified',
        'is_active', 'last_login', 'date_joined'
    ]
    list_filter = [
        'is_active', 'is_staff', 'is_superuser', 'role', 
        'date_joined', 'last_login'
    ]
    search_fields = ['email', 'first_name', 'last_name', 'username']
    ordering = ['-date_joined']
    readonly_fields = ['id', 'date_joined', 'last_login', 'email_verified', 'profile_completed']
    
    fieldsets = (
        (None, {
            'fields': ('email', 'password')
        }),
        ('Personal info', {
            'fields': ('first_name', 'last_name', 'username')
        }),
        ('Profile Info', {
            'fields': ('auth_provider', 'email_verified', 'profile_completed', 'bio', 'organization', 'location', 'website', 'github_username', 'avatar_url'),
            'classes': ('collapse',)
        }),
        ('Additional Data', {
            'fields': ('profile_data',),
            'classes': ('collapse',)
        }),
        ('Permissions', {
            'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
        ('System Info', {
            'fields': ('id',),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'role'),
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('role')