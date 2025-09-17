
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
import os

from drf_spectacular.views import SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

# from src.apps.content.views import ResourceViewSet
# from src.apps.content.asset_views import (
#     AssetListView, AssetDetailView, AssetRequestAccessView, AssetDownloadView,
#     asset_access_status, asset_related
# )
# from src.apps.content.publisher_views import (
#     PublisherDetailView, publisher_assets, publisher_statistics,
#     publisher_list, publisher_members
# )


def health_check(request):
    """Simple health check endpoint for deployment verification"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'Itqan CMS API',
        'timestamp': str(timezone.now())
    })


def serve_openapi_spec(request):
    """Serve the static OpenAPI specification file"""
    try:
        # Path to the openapi.yaml file
        openapi_path = os.path.join(settings.BASE_DIR, 'openapi.yaml')
        
        with open(openapi_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Return YAML content type
        return HttpResponse(content, content_type='application/x-yaml')
            
    except FileNotFoundError:
        return JsonResponse({'error': 'OpenAPI specification not found'}, status=404)
router = DefaultRouter()

# router.register(r'resources', ResourceViewSet, basename='resource')

urlpatterns = [
    # Legacy Swagger/ReDoc (for compatibility)
    path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Health check endpoint
    path('health/', health_check, name='health_check'),
    
    # OpenAPI Specification
    path('openapi.yaml', serve_openapi_spec, name='openapi-yaml'),
    
    # Django Admin
    path('django-admin/', admin.site.urls),
    
    # Wagtail CMS removed - using Django Admin in V1
    
    # API Routes (optional include if module exists)
    
    # Mock API endpoints (dummy data for development/testing)
    path('mock-api/', include('mock_api.urls')),
    
    # Django Allauth URLs
    path('accounts/', include('allauth.urls')),
    
    # FIXME move to apps/content/urls.py
    # path('assets/', AssetListView.as_view(), name='asset_list'),
    # path('assets/<int:asset_id>/', AssetDetailView.as_view(), name='asset_detail'),
    # path('assets/<int:asset_id>/request-access/', AssetRequestAccessView.as_view(), name='asset_request_access'),
    # path('assets/<int:asset_id>/download/', AssetDownloadView.as_view(), name='asset_download'),
    # path('assets/<int:asset_id>/access-status/', asset_access_status, name='asset_access_status'),
    # path('assets/<int:asset_id>/related/', asset_related, name='asset_related'),
    #
    # # Publisher endpoints (Publisher-based)
    # path('publishers/', publisher_list, name='publisher_list'),
    # path('publishers/<int:publisher_id>/', PublisherDetailView.as_view(), name='publisher_detail'),
    # path('publishers/<int:publisher_id>/assets/', publisher_assets, name='publisher_assets'),
    # path('publishers/<int:publisher_id>/statistics/', publisher_statistics, name='publisher_statistics'),
    # path('publishers/<int:publisher_id>/members/', publisher_members, name='publisher_members'),

]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Django Debug Toolbar
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns