"""
Itqan CMS URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
# Wagtail removed - using Django Admin in V1
import os

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


urlpatterns = [
    # Health check endpoint
    path('health/', health_check, name='health_check'),
    
    # OpenAPI Specification
    path('openapi.yaml', serve_openapi_spec, name='openapi-yaml'),
    
    # Django Admin
    path('django-admin/', admin.site.urls),
    
    # Wagtail CMS removed - using Django Admin in V1
    
    # API Routes
    path('api/v1/', include('apps.api.urls')),
    
    # Authentication
    path('api/v1/auth/', include('apps.accounts.urls')),
    
    # Mock API endpoints (dummy data for development/testing)
    path('mock-api/', include('mock_api.urls')),
    
    # Django Allauth URLs
    path('accounts/', include('allauth.urls')),
    
    # Media Library
    path('', include('apps.medialib.urls')),
    
    # Wagtail frontend removed - using Django Admin in V1
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