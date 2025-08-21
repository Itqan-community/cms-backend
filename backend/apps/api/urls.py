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
from apps.content.views import ResourceViewSet, DistributionViewSet
from apps.licensing.views import LicenseViewSet, AccessRequestViewSet
from apps.analytics.views import UsageEventViewSet

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
    
    # Search endpoints
    path('search/', include('apps.search.urls')),
    
    # Authentication endpoints  
    path('auth/', include('apps.authentication.urls')),
]
