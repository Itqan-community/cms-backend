from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from oauth2_provider.urls import base_urlpatterns
from oauth2_provider.views import TokenView as DefaultTokenView

from config.cms_api import cms_api, cms_auth_api
from config.developers_api import developers_api
from config.portal_api import portal_api
from config.tenant_api import tenant_api


def health_check(request):
    """Simple health check endpoint for deployment verification"""
    return JsonResponse(
        {
            "status": "healthy",
            "service": "Itqan CMS API",
            "timestamp": str(timezone.now()),
        }
    )


# Override TokenView to force grant_type=client_credentials
class CustomTokenView(DefaultTokenView):
    """
    Overrides grant_type to always use client_credentials.
    This allows any input grant_type to be accepted at the endpoint level.
    """
    
    def post(self, request, *args, **kwargs):
        # Force grant_type to client_credentials
        post_data = request.POST.copy()
        post_data["grant_type"] = "client_credentials"
        request._post = post_data
        
        # Call parent post
        return super().post(request, *args, **kwargs)


# Build custom oauth2 patterns
oauth2_patterns = []
for pattern in base_urlpatterns:
    # Replace the token pattern with our custom view
    if hasattr(pattern, 'name') and pattern.name == 'token':
        oauth2_patterns.append(
            path("token/", csrf_exempt(CustomTokenView.as_view()), name="token")
        )
    else:
        oauth2_patterns.append(pattern)


urlpatterns = [
    path("health/", health_check, name="health_check"),
    # Django Admin
    path("django-admin/", admin.site.urls),
    # Django Allauth URLs
    path("accounts/", include("allauth.urls")),
    path("accounts/profile/", TemplateView.as_view(template_name="profile.html")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("o/", include(oauth2_patterns)),
    # Internal API mount
    path("cms-api/", cms_api.urls),
    # Tenant API mount
    path("tenant/", tenant_api.urls),
    # Portal API mount
    path("portal/", portal_api.urls),
    # Public developers API mount
    path("", developers_api.urls),
    path("cms-api/auth/", include("allauth.headless.urls")),
    path("cms-api/auth/", cms_auth_api.urls),  # just to show documentation
]

if settings.SAML_IDP_ENABLED:
    urlpatterns += [
        path("idp/", include("djangosaml2idp.urls")),
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
