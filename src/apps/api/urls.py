"""
API URL Configuration for Itqan CMS
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

# Import ViewSets
from apps.accounts.views import RoleViewSet, UserViewSet
from apps.content.views import ResourceViewSet, DistributionViewSet, WorkflowViewSet, workflow_permissions
from apps.licensing.views import LicenseViewSet, AccessRequestViewSet
from apps.analytics.views import UsageEventViewSet
from apps.medialib.views import MediaFileViewSet, MediaFolderViewSet, MediaAttachmentViewSet
from apps.api_keys.views import APIKeyViewSet, APIKeyUsageViewSet, RateLimitEventViewSet, APIKeyStatisticsViewSet

# Import Landing Page Views
from apps.api.views.landing import platform_statistics, platform_features, recent_content

# Import Content Standards Views
from apps.api.views.content_standards import ContentStandardsView, content_standards_simple

# Import Asset Views
from apps.content.asset_views import (
    AssetListView, AssetDetailView, AssetRequestAccessView, AssetDownloadView
)

# Create API router
router = DefaultRouter()

# Register ViewSets
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'users', UserViewSet, basename='user')
router.register(r'resources', ResourceViewSet, basename='resource')
router.register(r'distributions', DistributionViewSet, basename='distribution')
router.register(r'licenses', LicenseViewSet, basename='license')
router.register(r'access-requests', AccessRequestViewSet, basename='accessrequest')
router.register(r'usage-events', UsageEventViewSet, basename='usageevent')

# Media Library ViewSets
router.register(r'media/files', MediaFileViewSet, basename='mediafile')
router.register(r'media/folders', MediaFolderViewSet, basename='mediafolder')
router.register(r'media/attachments', MediaAttachmentViewSet, basename='mediaattachment')

# Workflow Management ViewSet
router.register(r'workflow', WorkflowViewSet, basename='workflow')

# API Key Management ViewSets
router.register(r'api-keys', APIKeyViewSet, basename='apikey')
router.register(r'api-keys-usage', APIKeyUsageViewSet, basename='apikeyusage')
router.register(r'rate-limit-events', RateLimitEventViewSet, basename='ratelimitevent')
router.register(r'api-stats', APIKeyStatisticsViewSet, basename='apikeystats')

# API URL patterns
urlpatterns = [
    # API Documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # JWT Authentication
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # API endpoints
    path('', include(router.urls)),
    
    # Landing page endpoints (public)
    path('landing/statistics/', platform_statistics, name='landing_statistics'),
    path('landing/features/', platform_features, name='landing_features'),
    path('landing/recent-content/', recent_content, name='landing_recent_content'),
    
    # Content Standards endpoints (public - ADMIN-002 / SF-04)
    path('content-standards/', ContentStandardsView.as_view(), name='content_standards'),
    path('content-standards/simple/', content_standards_simple, name='content_standards_simple'),
    
    # Workflow endpoints
    path('workflow/permissions/', workflow_permissions, name='workflow_permissions'),
    
    # Search endpoints
    path('search/', include('apps.search.urls')),
    
    # Asset endpoints (simplified frontend interface)
    path('assets/', AssetListView.as_view(), name='asset_list'),
    path('assets/<uuid:asset_id>/', AssetDetailView.as_view(), name='asset_detail'),
    path('assets/<uuid:asset_id>/request-access/', AssetRequestAccessView.as_view(), name='asset_request_access'),
    path('assets/<uuid:asset_id>/download/', AssetDownloadView.as_view(), name='asset_download'),
    
    # Authentication endpoints are in main config/urls.py under /api/v1/auth/
    # Using django-allauth based authentication
]
