"""
Mock API app URL configuration
"""

from django.urls import path
from . import views
from .asset_views import (
    list_assets, get_asset_details, request_asset_access, download_asset
)
from .other_views import (
    get_publisher_details, download_resource, get_license_by_code, 
    list_licenses, get_content_standards, get_app_config, health_check
)

app_name = 'mock_api'

urlpatterns = [
    # Authentication endpoints
    path('auth/register', views.register_user, name='register'),
    path('auth/login', views.login_user, name='login'),
    path('auth/oauth/google/start', views.oauth_google_start, name='oauth_google_start'),
    path('auth/oauth/github/start', views.oauth_github_start, name='oauth_github_start'),
    path('auth/oauth/google/callback', views.oauth_google_callback, name='oauth_google_callback'),
    path('auth/oauth/github/callback', views.oauth_github_callback, name='oauth_github_callback'),
    path('auth/profile', views.get_user_profile, name='get_user_profile'),
    path('auth/token/refresh', views.refresh_token, name='refresh_token'),
    path('auth/logout', views.logout_user, name='logout'),
    
    # Development helper endpoints
    path('auth/test-users', views.list_test_users, name='list_test_users'),
    
    # Assets endpoints
    path('assets', list_assets, name='list_assets'),
    path('assets/<int:asset_id>', get_asset_details, name='get_asset_details'),
    path('assets/<int:asset_id>/request-access', request_asset_access, name='request_asset_access'),
    path('assets/<int:asset_id>/download', download_asset, name='download_asset'),
    
    # Publishers endpoints
    path('publishers/<int:publisher_id>', get_publisher_details, name='get_publisher_details'),
    
    # Resources endpoints
    path('resources/<int:resource_id>/download', download_resource, name='download_resource'),
    
    # Licenses endpoints
    path('licenses/<str:license_code>', get_license_by_code, name='get_license_by_code'),
    path('licenses', list_licenses, name='list_licenses'),
    
    # Content Standards endpoints
    path('content-standards', get_content_standards, name='get_content_standards'),
    
    # System endpoints
    path('config', get_app_config, name='get_app_config'),
    path('health', health_check, name='health_check'),
]
