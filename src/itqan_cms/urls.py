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
import yaml
import json
import os

def health_check(request):
    """Simple health check endpoint for deployment verification"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'Itqan CMS API',
        'timestamp': str(timezone.now())
    })

def openapi_spec(request, format_type='json'):
    """Serve OpenAPI specification from static YAML file"""
    try:
        # Path to the OpenAPI YAML file
        openapi_file_path = os.path.join(settings.BASE_DIR, 'openapi.yaml')
        
        with open(openapi_file_path, 'r', encoding='utf-8') as file:
            spec_data = yaml.safe_load(file)
        
        if format_type == 'yaml':
            response = HttpResponse(
                yaml.dump(spec_data, default_flow_style=False),
                content_type='application/x-yaml'
            )
            response['Content-Disposition'] = 'inline; filename="openapi.yaml"'
            return response
        else:  # json format
            return JsonResponse(spec_data, json_dumps_params={'indent': 2})
            
    except FileNotFoundError:
        return JsonResponse({'error': 'OpenAPI specification file not found'}, status=404)
    except yaml.YAMLError as e:
        return JsonResponse({'error': f'Error parsing OpenAPI specification: {str(e)}'}, status=500)

def swagger_ui_view(request):
    """Swagger UI view that uses our static OpenAPI spec"""
    # Get the base URL for the OpenAPI spec
    base_url = f"{request.scheme}://{request.get_host()}"
    spec_url = f"{base_url}/swagger.json"
    
    # Generate Swagger UI HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Itqan CMS API - Swagger UI</title>
        <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css" />
        <style>
            html {{
                box-sizing: border-box;
                overflow: -moz-scrollbars-vertical;
                overflow-y: scroll;
            }}
            *, *:before, *:after {{
                box-sizing: inherit;
            }}
            body {{
                margin:0;
                background: #fafafa;
            }}
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
        <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-standalone-preset.js"></script>
        <script>
            window.onload = function() {{
                const ui = SwaggerUIBundle({{
                    url: "{spec_url}",
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
                }});
            }};
        </script>
    </body>
    </html>
    """
    
    return HttpResponse(html, content_type='text/html')

def redoc_view(request):
    """ReDoc view that uses our static OpenAPI spec"""
    # Get the base URL for the OpenAPI spec
    base_url = f"{request.scheme}://{request.get_host()}"
    spec_url = f"{base_url}/swagger.json"
    
    # Generate ReDoc HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Itqan CMS API - Documentation</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
        <style>
            body {{
                margin: 0;
                padding: 0;
            }}
        </style>
    </head>
    <body>
        <redoc spec-url="{spec_url}"></redoc>
        <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
    </body>
    </html>
    """
    
    return HttpResponse(html, content_type='text/html')

urlpatterns = [
    # Health check endpoint
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('api/v1/', include('core.urls')),
    
    # OpenAPI Specification from static file
    re_path(r'^swagger\.json$', openapi_spec, {'format_type': 'json'}, name='openapi-json'),
    re_path(r'^swagger\.yaml$', openapi_spec, {'format_type': 'yaml'}, name='openapi-yaml'),
    
    # Swagger UI and ReDoc using static spec
    path('swagger/', swagger_ui_view, name='swagger-ui'),
    path('redoc/', redoc_view, name='redoc'),
    
    # Keep legacy endpoints for compatibility
    path('docs/', swagger_ui_view, name='api-docs'),
]

# Add static/media URL patterns for development
if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    if hasattr(settings, 'MEDIA_URL'):
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
