import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.urls import include, path
from django.utils import timezone
from oauth2_provider import urls as oauth2_urls
from rest_framework.routers import DefaultRouter

from config.cms_api import cms_api
from config.developers_api import deprecated_developers_api, developers_api


def health_check(request):
    """Simple health check endpoint for deployment verification"""
    return JsonResponse(
        {
            "status": "healthy",
            "service": "Itqan CMS API",
            "timestamp": str(timezone.now()),
        }
    )


def serve_openapi_spec(request):
    """Serve the static OpenAPI specification file"""
    try:
        # Path to the openapi.yaml file
        openapi_path = os.path.join(settings.BASE_DIR, "openapi.yaml")

        with open(openapi_path, encoding="utf-8") as f:
            content = f.read()

        # Return YAML content type
        return HttpResponse(content, content_type="application/x-yaml")

    except FileNotFoundError:
        return JsonResponse({"error": "OpenAPI specification not found"}, status=404)


router = DefaultRouter()


urlpatterns = [
    path("health/", health_check, name="health_check"),
    # Django Admin
    path("django-admin/", admin.site.urls),
    # Django Allauth URLs
    path("accounts/", include("allauth.urls")),
    path("o/", include(oauth2_urls)),
    # Internal CMS API mount
    path("cms-api/", cms_api.urls),
    # Public developers API mount
    path("developers-api/", deprecated_developers_api.urls),
    path("", developers_api.urls),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Django Debug Toolbar
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
