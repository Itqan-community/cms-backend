"""
URL configuration for itqan_cms project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

def health_check(request):
    """Simple health check endpoint for deployment verification"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'Itqan CMS API',
        'timestamp': str(timezone.now())
    })

# Swagger/OpenAPI Schema
schema_view = get_schema_view(
    openapi.Info(
        title="Itqan CMS API",
        default_version='v1',
        description="Content Management System API for Itqan platform",
        terms_of_service="https://www.itqan.com/terms/",
        contact=openapi.Contact(email="api@itqan.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # Health check endpoint
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('api/v1/', include('core.urls')),
    
    # Swagger/OpenAPI Documentation
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    re_path(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    re_path(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API Documentation root
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api-docs'),
]

# Add static/media URL patterns for development
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    if hasattr(settings, 'MEDIA_URL'):
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
