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
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
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
        
        # Determine content type based on request format
        if request.path.endswith('.json'):
            # If JSON is requested, we would need to convert YAML to JSON
            # For now, return YAML with appropriate content type
            return HttpResponse(content, content_type='application/x-yaml')
        else:
            return HttpResponse(content, content_type='application/x-yaml')
            
    except FileNotFoundError:
        return JsonResponse({'error': 'OpenAPI specification not found'}, status=404)

def swagger_ui_view(request):
    """Custom Swagger UI view that uses our static OpenAPI specification"""
    swagger_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Itqan CMS API Documentation</title>
        <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.10.3/swagger-ui.css" />
        <style>
            html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
            *, *:before, *:after { box-sizing: inherit; }
            body { margin:0; background: #fafafa; }
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5.10.3/swagger-ui-bundle.js"></script>
        <script src="https://unpkg.com/swagger-ui-dist@5.10.3/swagger-ui-standalone-preset.js"></script>
        <script>
        window.onload = function() {
            const ui = SwaggerUIBundle({
                url: '/openapi.yaml',
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout"
            });
        };
        </script>
    </body>
    </html>
    '''
    return HttpResponse(swagger_html, content_type='text/html')

def redoc_ui_view(request):
    """Custom ReDoc UI view that uses our static OpenAPI specification"""
    redoc_html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Itqan CMS API Documentation</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
        <style>
            body { margin: 0; padding: 0; }
        </style>
    </head>
    <body>
        <redoc spec-url='/openapi.yaml'></redoc>
        <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js"></script>
    </body>
    </html>
    '''
    return HttpResponse(redoc_html, content_type='text/html')

urlpatterns = [
    # Health check endpoint
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('api/v1/', include('core.urls')),
    
    # Mock API endpoints (dummy data)
    path('mock-api/', include('mock_api.urls')),
    
    # Static OpenAPI Specification (serves our custom openapi.yaml)
    path('openapi.yaml', serve_openapi_spec, name='openapi-yaml'),
    path('openapi.json', serve_openapi_spec, name='openapi-json'),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', serve_openapi_spec, name='static-schema'),
    
    # Custom Swagger/OpenAPI Documentation UI (using static spec)
    re_path(r'^swagger/$', swagger_ui_view, name='schema-swagger-ui'),
    re_path(r'^redoc/$', redoc_ui_view, name='schema-redoc'),
    
    # API Documentation root
    path('docs/', swagger_ui_view, name='api-docs'),
]

# Add static/media URL patterns for development
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    if hasattr(settings, 'MEDIA_URL'):
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
