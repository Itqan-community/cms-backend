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
# from apps.licensing.views import LicenseViewSet, AccessRequestViewSet  # Temporarily disabled
from apps.analytics.views import UsageEventViewSet
from apps.medialib.views import MediaFileViewSet, MediaFolderViewSet, MediaAttachmentViewSet
from apps.api_keys.views import APIKeyViewSet, APIKeyUsageViewSet, RateLimitEventViewSet, APIKeyStatisticsViewSet

# Import Landing Page Views
from apps.api.views.landing import platform_statistics, platform_features, recent_content

# Import Content Standards Views
from apps.api.views.content_standards import ContentStandardsView, content_standards_simple

# Import Asset Views
from apps.content.asset_views import (
    AssetListView, AssetDetailView, AssetRequestAccessView, AssetDownloadView,
    asset_access_status, asset_related
)

# Import Publisher Views  
from apps.content.publisher_views import (
    PublisherDetailView, publisher_assets, publisher_statistics, 
    publisher_list, publisher_members
)

# Import License Views
from apps.content.license_views import (
    LicenseListView, LicenseDetailView, license_usage_statistics,
    license_terms, search_licenses, default_license
)

# Create API router
router = DefaultRouter()

# Register ViewSets
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'users', UserViewSet, basename='user')
router.register(r'resources', ResourceViewSet, basename='resource')
router.register(r'distributions', DistributionViewSet, basename='distribution')
# router.register(r'licenses', LicenseViewSet, basename='license')  # Temporarily disabled
# router.register(r'access-requests', AccessRequestViewSet, basename='accessrequest')  # Temporarily disabled
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
    
    # Asset endpoints (ERD-aligned implementation)
    path('assets/', AssetListView.as_view(), name='asset_list'),
    path('assets/<int:asset_id>/', AssetDetailView.as_view(), name='asset_detail'),
    path('assets/<int:asset_id>/request-access/', AssetRequestAccessView.as_view(), name='asset_request_access'),
    path('assets/<int:asset_id>/download/', AssetDownloadView.as_view(), name='asset_download'),
    path('assets/<int:asset_id>/access-status/', asset_access_status, name='asset_access_status'),
    path('assets/<int:asset_id>/related/', asset_related, name='asset_related'),
    
    # Publisher endpoints (PublishingOrganization-based)
    path('publishers/', publisher_list, name='publisher_list'),
    path('publishers/<int:publisher_id>/', PublisherDetailView.as_view(), name='publisher_detail'),
    path('publishers/<int:publisher_id>/assets/', publisher_assets, name='publisher_assets'),
    path('publishers/<int:publisher_id>/statistics/', publisher_statistics, name='publisher_statistics'),
    path('publishers/<int:publisher_id>/members/', publisher_members, name='publisher_members'),
    
    # License endpoints
    path('licenses/', LicenseListView.as_view(), name='license_list'),
    path('licenses/default/', default_license, name='default_license'),
    path('licenses/search/', search_licenses, name='search_licenses'),
    path('licenses/<str:license_code>/', LicenseDetailView.as_view(), name='license_detail'),
    path('licenses/<str:license_code>/statistics/', license_usage_statistics, name='license_usage_statistics'),
    path('licenses/<str:license_code>/terms/', license_terms, name='license_terms'),
    
    # Authentication endpoints are in main config/urls.py under /api/v1/auth/
    # Using django-allauth based authentication
]
